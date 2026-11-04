from kickoff.models import Participant


def test_only_explicit_national_team_country_code_crosses_public_boundary():
    from kickoff.web import _participant_payload

    assert _participant_payload(
        Participant(name="Japan", entity_type="national_team", metadata={"country_code": "JP", "private": "hidden"})
    ) == {
        "name": "Japan",
        "participant_id": None,
        "short_name": None,
        "role": None,
        "entity_type": "national_team",
        "country_code": "JP",
    }
    for entity, country in [("team", "JP"), ("club", "JP"), ("national_team", "Japan"), ("national_team", None)]:
        published = _participant_payload(
            Participant(name="Japan", entity_type=entity, metadata={"country_code": country})
        )
        assert "country_code" not in published
        assert "metadata" not in published
