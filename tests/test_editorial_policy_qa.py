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


def test_duplicate_paragraphs_are_blocked():
    repeated = "A distinct paragraph with a factual explanation and meaningful detail."
    script = "\n\n".join([repeated] * 500)
    result = run_package_qa(_package(script), {"review_risk": "standard"})
    duplicate_check = next(item for item in result["checks"] if item["check"] == "duplicate_paragraphs")
    assert duplicate_check["passed"] is False
    assert result["passed"] is False


def test_originality_and_viewer_payoff_are_required():
    package = _package(" ".join(["Evidence explains the underlying mechanism."] * 1000))
    package["original_angle"] = ""
    package["viewer_payoff"] = ""
    result = run_package_qa(package, {"review_risk": "standard"})
    failed = {item["check"] for item in result["errors"]}
    assert "original_editorial_angle" in failed
    assert "viewer_payoff" in failed


def test_high_risk_requires_three_sources():
    package = _package(" ".join(["Evidence explains the underlying mechanism."] * 1000))
    package["research"] = package["research"][:2]
    result = run_package_qa(package, {"review_risk": "high"})
    research_check = next(item for item in result["checks"] if item["check"] == "research_depth")
    assert research_check["passed"] is False



def test_shopping_is_optional_and_not_assumed_eligible():
    package = _package(" ".join(["Evidence explains the underlying mechanism."] * 1000))
    package["shopping"] = {
        "recommended": False,
        "product_candidates": [],
        "eligibility_verified_in_studio": False,
        "product_tagging_status": "not_started",
        "disclosure_review_required": True,
        "native_affiliate_links_external_distribution_allowed": False,
    }
    result = run_package_qa(package, {"review_risk": "standard"})
    assert result["passed"] is True or all(
        item["check"] != "shopping_product_evidence" for item in result["checks"]
    )


def test_shopping_product_requires_verified_relevance_and_offer():
    package = _package(" ".join(["Evidence explains the underlying mechanism."] * 1000))
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
