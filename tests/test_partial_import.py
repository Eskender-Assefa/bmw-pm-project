from pathlib import Path

import pytest
from sqlalchemy import func, select

from backend.ingestion import import_files
from backend.models import EvidenceRef, Feedback, Source


ROOT = Path(__file__).resolve().parents[1]
FILES = ['G60_OptionList.PDF', 'BMW_G60_Scopes_and_Data.pdf',
         '261010_BMW_Product_Management_Key_Note(1).pptx', 'G60_feedback_hackathon.xlsx']


def test_partial_reimport_preserves_records_and_rejects_replacements(session, tmp_path):
    before = session.scalar(select(func.count()).select_from(EvidenceRef))
    result = import_files(session, [ROOT / name for name in FILES])
    session.commit()
    assert result == {'imported': [], 'skipped': FILES}
    assert session.scalar(select(func.count()).select_from(EvidenceRef)) == before
    assert session.scalar(select(func.count()).select_from(Feedback).where(Feedback.model == 'G60')) == 4000
    changed = tmp_path / 'G60_feedback_hackathon.xlsx'
    changed.write_bytes(b'changed source edition')
    with pytest.raises(ValueError, match='new checksum'):
        import_files(session, [changed])
    unsupported = tmp_path / 'unrecognized.pdf'
    unsupported.write_bytes(b'unrecognized source')
    with pytest.raises(ValueError, match='Unsupported source'):
        import_files(session, [unsupported])


def test_project_references_are_searchable_and_original_deck_downloads(client):
    sources = client.get('/api/v1/sources').json()
    for name, count in [(FILES[1], 28), (FILES[2], 4)]:
        source = next(s for s in sources if s['filename'] == name)
        response = client.get('/api/v1/evidence', params={'source_id': source['id'], 'kind': 'project_reference'})
        assert response.status_code == 200
        assert response.json()['total'] == count
        assert all(item['model'] == 'G60' for item in response.json()['items'])
        if source['format'] == 'pptx':
            assert all('slide' in item['locator'] for item in response.json()['items'])
            original = client.get('/api/v1/sources/' + source['id'] + '/file')
            assert original.status_code == 200
            assert original.headers['content-type'] == 'application/vnd.openxmlformats-officedocument.presentationml.presentation'
