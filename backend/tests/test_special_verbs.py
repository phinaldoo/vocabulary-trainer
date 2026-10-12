import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from test_api_workflows import _mutation_headers, _register, _settings

from app.main import create_app
from app.models import Card, Deck, UserCardProgress
from app.services.answer_matcher import match_card_answer
from app.services.special_verbs import parse_verb_csv, verb_manifest

CSV = '''Verben der a-Konjugaton;;;;
u-Perfekt;;;;
vetare;veto;vetui;vetitum;verbieten
;;;;
Dehnungsperfekt;;;;
stare;sto;steti;-;stehen
Verben der e-Konjugaton;;;;
u-Perfekt;;;;
censere;censeo;censui;(censum);meinen, einschätzen
'''


def test_grouped_csv_and_stable_import_identity():
    parsed = parse_verb_csv('\ufeff' + CSV + 'u-Perfekt;;;;\ndocere;doceo;docui;doctum;lehren\n')
    assert not parsed.errors
    assert len(parsed.rows) == 4
    assert parsed.section_count == 3
    assert parsed.rows[1].supine == '-'
    manifest = verb_manifest('Test verbs', parsed.rows)
    assert len(manifest.sections) == 3
    assert manifest.cards[2].front.text == 'censere, censeo, censui, (censum)'
    assert manifest.cards[2].back.text == 'meinen, einschätzen'
    assert manifest.cards[0].metadata == {
        'additional_info': 'Verben der a-Konjugaton', 'additional_info_2': 'u-Perfekt',
    }
    again = parse_verb_csv(CSV.replace('\n', '\r\n'))
    original = parse_verb_csv(CSV)
    assert verb_manifest('Renamed', again.rows).id == verb_manifest('Original', original.rows).id


@pytest.mark.parametrize('text', [
    'Infinitiv;Präsens;Perfekt;Supinum;Deutsch\nvetare;veto;vetui;vetitum;"verbieten; untersagen"',
    'infinitive,present,perfect,supine,meaning\nvetare,veto,vetui,vetitum,"verbieten, untersagen"',
    'vetare\tveto\tvetui\tvetitum\tverbieten',
    'vetare,veto,vetui,vetitum,"verbieten; untersagen"',
    'Verben der a-Konjugaton\nu-Perfekt\nvetare;veto;vetui;vetitum;verbieten',
])
def test_delimiters_headers_and_quoted_meanings(text):
    parsed = parse_verb_csv(text)
    assert not parsed.errors
    assert len(parsed.rows) == 1


@pytest.mark.parametrize(('text', 'code'), [
    ('vetare;veto;vetui;verbieten', 'columns'),
    ('vetare;veto;;vetitum;verbieten', 'required'),
    ('vetare;;;;', 'required'),
    ('vetare;veto;vetui;vetitum;"unclosed', 'syntax'),
    (';;;;\n', 'empty'),
    ('vetare;veto;vetui;vetitum;(verbieten', 'answer'),
    ('vetare;veto;vetui;vetitum;\x00', 'encoding'),
    ('vetare;veto;vetui;vetitum;' + 'a' * 251, 'length'),
])
def test_malformed_rows_are_reported(text, code):
    assert parse_verb_csv(text).errors[0].code == code


def test_duplicates_are_not_silently_overwritten():
    row = 'vetare;veto;vetui;vetitum;verbieten\n'
    parsed = parse_verb_csv(row * 2)
    assert len(parsed.rows) == 1
    assert parsed.duplicate_count == 1
    assert not parsed.errors
    conflict = parse_verb_csv(row + row.replace('verbieten', 'geben'))
    assert conflict.errors[0].code == 'duplicate'
    assert conflict.errors[0].line == 2


@pytest.mark.parametrize(('answer', 'expected', 'correct'), [
    ('vetare', 'vetare, veto, vetui, vetitum', False),
    ('vetare veto vetui', 'vetare, veto, vetui, vetitum', False),
    ('vetare vetui veto vetitum', 'vetare, veto, vetui, vetitum', False),
    ('VETARE; veto; vetui; vetitum', 'vetare, veto, vetui, vetitum', True),
    ('censere censeo censui censum', 'censere, censeo, censui, (censum)', True),
    ('censere censeo censui', 'censere, censeo, censui, (censum)', False),
    ('stare sto steti', 'stare, sto, steti, -', True),
    ('cernere cerno', 'cernere, cerno, -, -', True),
])
def test_principal_parts_require_all_forms_in_order(answer, expected, correct):
    assert match_card_answer(
        answer, expected, [], matcher_profile='latin-principal-parts-v1',
    ).correct is correct


@pytest.mark.asyncio
async def test_csv_import_and_both_directions_persist_isolated_progress():
    app = create_app(_settings())
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://testserver') as admin:
            owner = await _register(admin, 'verbs-owner@example.com')
            payload = {'title': 'Verbs', 'csv_text': CSV}
            headers = _mutation_headers(admin)
            preview = await admin.post('/api/v1/admin/special-verbs/preview',
                                       json=payload, headers=headers)
            assert preview.status_code == 200
            assert len(preview.json()['rows']) == 3
            async with app.state.session_factory() as db:
                assert await db.scalar(select(func.count()).select_from(Deck)) == 0
            invalid = await admin.post('/api/v1/admin/special-verbs/import', headers=headers,
                                       json={**payload, 'csv_text': CSV + 'bad;row\n'})
            assert invalid.status_code == 422
            imported = await admin.post('/api/v1/admin/special-verbs/import',
                                        json=payload, headers=headers)
            assert imported.status_code == 200, imported.text
            deck = imported.json()['deck']
            assert deck['status'] == 'published'
            assert deck['card_count'] == 3
            sections = (await admin.get(f"/api/v1/sections?deck_id={deck['id']}")).json()
            for direction in ['forward', 'reverse']:
                started = await admin.post('/api/v1/study-sessions', headers=headers, json={
                    'deck_id': deck['id'], 'section_ids': [sections[0]['id']],
                    'direction': direction, 'input_mode': 'typing', 'limit': 1,
                })
                assert started.status_code == 200, started.text
                session = started.json()
                card = session['cards'][0]
                expected_prompt = (
                    'vetare, veto, vetui, vetitum' if direction == 'forward' else 'verbieten'
                )
                assert card['prompt'] == expected_prompt
                if direction == 'reverse':
                    wrong = await admin.post(
                        f"/api/v1/study-sessions/{session['id']}/check", headers=headers,
                        json={'item_id': card['item_id'], 'answer': 'vetare'},
                    )
                    assert wrong.json()['correct'] is False
                answer = 'verbieten' if direction == 'forward' else 'vetare veto vetui vetitum'
                checked = await admin.post(
                    f"/api/v1/study-sessions/{session['id']}/check", headers=headers,
                    json={'item_id': card['item_id'], 'answer': answer},
                )
                assert checked.json()['correct'] is True
                reviewed = await admin.post(
                    f"/api/v1/study-sessions/{session['id']}/reviews", headers=headers, json={
                        'item_id': card['item_id'], 'base_version': card['state_version'],
                        'idempotency_key': str(uuid.uuid4()),
                        'response': {'type': 'typing', 'answer': answer, 'rating': 2},
                    },
                )
                assert reviewed.status_code == 200, reviewed.text
                assert reviewed.json()['complete'] is True
                resumed = (await admin.get(f"/api/v1/study-sessions/{session['id']}")).json()
                assert resumed['complete'] is True
            again = await admin.post('/api/v1/admin/special-verbs/import', headers=headers,
                                     json={**payload, 'title': 'Renamed file'})
            assert again.json()['unchanged'] is True
            assert again.json()['deck']['id'] == deck['id']
            async with app.state.session_factory() as db:
                assert await db.scalar(select(func.count()).select_from(Deck)) == 1
                assert await db.scalar(select(func.count()).select_from(Card)) == 3
                progress = list((await db.scalars(select(UserCardProgress))).all())
                assert len(progress) == 2
                assert {p.direction for p in progress} == {'forward', 'reverse'}
                assert all(str(p.user_id) == owner['id'] for p in progress)
            async with AsyncClient(transport=transport, base_url='http://testserver') as learner:
                await _register(learner, 'verbs-learner@example.com')
                for action in ['preview', 'import']:
                    denied = await learner.post(f'/api/v1/admin/special-verbs/{action}',
                                                headers=_mutation_headers(learner), json=payload)
                    assert denied.status_code == 403
                assert (await learner.get('/api/v1/decks')).json()[0]['id'] == deck['id']
                started = await learner.post('/api/v1/study-sessions',
                                             headers=_mutation_headers(learner), json={
                    'deck_id': deck['id'], 'direction': 'mixed', 'input_mode': 'reveal', 'limit': 3,
                })
                assert started.status_code == 200
                session = started.json()
                assert len(session['cards']) == 3
                assert all(card['is_new'] for card in session['cards'])
                card = session['cards'][0]
                revealed = await learner.post(
                    f"/api/v1/study-sessions/{session['id']}/items/{card['item_id']}/reveal",
                    headers=_mutation_headers(learner),
                )
                assert revealed.status_code == 200
                assert revealed.json()['solution']
