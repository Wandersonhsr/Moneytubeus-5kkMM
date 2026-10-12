from app.editorial.qa import run_package_qa


def _package(script: str) -> dict:
    sources = [
        {"title": "Primary source", "url": "https://www.sec.gov/example", "publisher": "SEC"},
        {"title": "Independent source", "url": "https://www.imf.org/example", "publisher": "IMF"},
        {"title": "Additional source", "url": "https://www.bls.gov/example", "publisher": "BLS"},
    ]
    summary = "This episode explains the documented mechanism and why it matters."
    return {
        "title": "The Hidden Mechanism Behind This Major Change",
        "script": script,
        "description": summary + "\n\nSources listed below.",
        "summary": summary,
        "original_angle": "Explain the second-order mechanism, not just the headline.",
        "viewer_payoff": "The viewer can explain the mechanism and its implications.",
        "tags": ["technology", "economics", "analysis", "systems", "documentary"],
        "research": sources,
        "visual_beats": [{"scene": 1}, {"scene": 2}, {"scene": 3}],
        "asset_manifest": [],
    }


def _valid_script() -> str:
    return " ".join(["Evidence explains the underlying mechanism."] * 250)


def test_duplicate_paragraphs_are_blocked():
    repeated = "A distinct paragraph with a factual explanation and meaningful detail."
    script = "\n\n".join([repeated] * 500)
    result = run_package_qa(_package(script), {"review_risk": "standard"})
    duplicate_check = next(item for item in result["checks"] if item["check"] == "duplicate_paragraphs")
    assert duplicate_check["passed"] is False
    assert result["passed"] is False


def test_originality_and_viewer_payoff_are_required():
    package = _package(_valid_script())
    package["original_angle"] = ""
    package["viewer_payoff"] = ""
    result = run_package_qa(package, {"review_risk": "standard"})
    failed = {item["check"] for item in result["errors"]}
    assert "original_editorial_angle" in failed
    assert "viewer_payoff" in failed


def test_high_risk_requires_three_sources():
    package = _package(_valid_script())
    package["research"] = package["research"][:2]
    result = run_package_qa(package, {"review_risk": "high"})
    research_check = next(item for item in result["checks"] if item["check"] == "research_depth")
    assert research_check["passed"] is False


def test_shopping_is_optional_and_not_assumed_eligible():
    package = _package(_valid_script())
    package["shopping"] = {
        "recommended": False,
        "product_candidates": [],
        "eligibility_verified_in_studio": False,
        "product_tagging_status": "not_started",
        "disclosure_review_required": True,
        "native_affiliate_links_external_distribution_allowed": False,
    }
    result = run_package_qa(package, {"review_risk": "standard"})
    shopping_checks = [
        item["check"] for item in result["checks"] if item["check"].startswith("shopping_")
    ]
    assert shopping_checks == []


def test_shopping_product_requires_verified_relevance_and_offer():
    package = _package(_valid_script())
    package["shopping"] = {
        "recommended": True,
        "product_candidates": [
            {"name": "Example item", "product_url": "https://merchant.example/item"}
        ],
        "eligibility_verified_in_studio": False,
        "product_tagging_status": "not_started",
        "disclosure_review_required": True,
    }
    result = run_package_qa(package, {"review_risk": "standard"})
    check = next(item for item in result["checks"] if item["check"] == "shopping_product_evidence")
    assert check["passed"] is False
    assert any(item["check"] == "shopping_product_evidence" for item in result["errors"])


def test_shopping_product_with_evidence_passes_product_check_but_requires_studio_review():
    package = _package(_valid_script())
    package["shopping"] = {
        "recommended": True,
        "product_candidates": [
            {
                "name": "Example item",
                "product_url": "https://merchant.example/item",
                "episode_relevance": "Demonstrates the specific workflow explained in the episode.",
                "offer_verified_at": "2026-10-12T10:00:00-03:00",
            }
        ],
        "eligibility_verified_in_studio": False,
        "product_tagging_status": "not_started",
        "disclosure_reviewed": False,
        "disclosure_review_required": True,
    }
    result = run_package_qa(package, {"review_risk": "standard"})
    product_check = next(
        item for item in result["checks"] if item["check"] == "shopping_product_evidence"
    )
    eligibility_check = next(
        item for item in result["checks"] if item["check"] == "shopping_eligibility_and_tagging"
    )
    disclosure_check = next(
        item for item in result["checks"] if item["check"] == "shopping_disclosure"
    )
    assert product_check["passed"] is True
    assert eligibility_check["passed"] is False
    assert disclosure_check["passed"] is False
    assert any(item["check"] == "shopping_eligibility_and_tagging" for item in result["warnings"])
    assert any(item["check"] == "shopping_disclosure" for item in result["warnings"])
