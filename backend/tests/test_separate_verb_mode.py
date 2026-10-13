import importlib.util
import uuid
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from httpx import ASGITransport, AsyncClient
from learner_fixtures import make_deck
from sqlalchemy import select
from test_api_workflows import _mutation_headers, _register, _settings
from test_special_verbs import CSV

from app.main import create_app
from app.models import Card, Deck, StudySession, User


async def import_verbs(client):
    response = await client.post('/api/v1/admin/special-verbs/import',
                                 headers=_mutation_headers(client),
                                 json={'title': 'Special verbs', 'csv_text': CSV})
    assert response.status_code == 200
    return response.json()['deck']


async def start(client, deck_id, **config):
    response = await client.post('/api/v1/study-sessions',
                                 headers=_mutation_headers(client), json={
        'deck_id': str(deck_id), 'direction': 'forward', 'input_mode': 'typing',
        'selection_mode': 'random', 'limit': 1, **config,
    })
    assert response.status_code == 200, response.text
    return response.json()


@pytest.mark.asyncio
async def test_special_verb_sessions_preserve_normal_chapters_and_preferences():
    app = create_app(_settings())
    async with app.router.lifespan_context(app):
        normal, sections, cards = await make_deck(app)
        async with AsyncClient(transport=ASGITransport(app=app),
                               base_url='http://testserver') as client:
            await _register(client, 'separate@example.com')
            selected = [str(sections[0].id), str(sections[2].id)]
            await start(client, normal.id, section_ids=selected, direction='mixed',
                        input_mode='reveal', selection_mode='adaptive')
            before = (await client.get('/api/v1/auth/me')).json()
            verb_deck = await import_verbs(client)
            assert [d['id'] for d in (await client.get('/api/v1/decks')).json()] == [
                str(normal.id),
            ]
            assert [d['id'] for d in (
                await client.get('/api/v1/decks?kind=special_verbs')
            ).json()] == [verb_deck['id']]
            assert len((await client.get('/api/v1/decks?kind=all')).json()) == 2
            verb_sections = (await client.get(
                f"/api/v1/sections?deck_id={verb_deck['id']}",
            )).json()
            for direction in ['forward', 'reverse', 'mixed']:
                verb_session = await start(client, verb_deck['id'], direction=direction,
                                           section_ids=[verb_sections[0]['id']])
                assert verb_session['kind'] == 'special_verbs'
                assert (await client.get('/api/v1/auth/me')).json() == before
                resumed = (await client.get(
                    f"/api/v1/study-sessions/{verb_session['id']}",
                )).json()
                assert resumed['kind'] == 'special_verbs'
                assert resumed['deck_id'] == verb_deck['id']
            assert (await client.get('/api/v1/dashboard')).json()['deck']['id'] == str(normal.id)
            assert (await client.get('/api/v1/progress')).json()['deck']['id'] == str(normal.id)
            assert {s['id'] for s in (await client.get('/api/v1/sections')).json()} == {
                str(s.id) for s in sections
            }
            assert {c['id'] for c in (await client.get('/api/v1/cards')).json()['items']} == {
                str(c.id) for c in cards
            }
            rejected = await client.patch('/api/v1/account/settings',
                                          headers=_mutation_headers(client), json={
                'daily_goal': 12, 'direction': 'forward', 'input_mode': 'typing',
                'selected_deck_id': verb_deck['id'],
            })
            assert rejected.status_code == 404
            assert (await client.get('/api/v1/auth/me')).json() == before


@pytest.mark.asyncio
async def test_default_endpoints_ignore_a_legacy_special_verb_selection():
    app = create_app(_settings())
    async with app.router.lifespan_context(app), AsyncClient(transport=ASGITransport(app=app),
                           base_url='http://testserver') as client:
        await _register(client, 'legacy@example.com')
        verbs = await import_verbs(client)
        async with app.state.session_factory() as db:
            user = await db.scalar(select(User))
            # Use the real UUID rather than the JSON serialization.
            user.selected_deck_id = await db.scalar(select(Deck.id))
            await db.commit()
        assert (await client.get('/api/v1/decks')).json() == []
        assert (await client.get('/api/v1/dashboard')).json()['deck'] is None
        assert (await client.get('/api/v1/sections')).json() == []
        normal, _, cards = await make_deck(app)
        assert (await client.get('/api/v1/dashboard')).json()['deck']['id'] == str(normal.id)
        assert (await client.get('/api/v1/progress')).json()['deck']['id'] == str(normal.id)
        assert (await client.get('/api/v1/cards')).json()['total'] == len(cards)
        # Explicit verb context remains available to the separate area.
        assert (await client.get(
            f"/api/v1/progress?deck_id={verbs['id']}",
        )).json()['deck']['id'] == verbs['id']


def run_repair(connection):
    path = (Path(__file__).parents[1]
            / 'alembic/versions/a51b6c7d8e90_restore_vocabulary_selection.py')
    spec = importlib.util.spec_from_file_location('restore_vocabulary_selection', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with Operations.context(MigrationContext.configure(connection)):
        module.upgrade()


@pytest.mark.asyncio
async def test_upgrade_recovers_latest_normal_session_without_changing_content():
    app = create_app(_settings())
    async with app.router.lifespan_context(app):
        first, _, _ = await make_deck(app, slug='first')
        last, sections, _ = await make_deck(app, slug='last')
        async with AsyncClient(transport=ASGITransport(app=app),
                               base_url='http://testserver') as client:
            await _register(client, 'recover@example.com')
            await start(client, first.id)
            selected = [str(sections[0].id), str(sections[1].id)]
            await start(client, last.id, section_ids=selected, direction='mixed',
                        input_mode='reveal', selection_mode='adaptive')
            expected = (await client.get('/api/v1/auth/me')).json()
            verbs = await import_verbs(client)
            verb_session = await start(client, verbs['id'])
            async with app.state.session_factory() as db:
                session = await db.get(StudySession, uuid.UUID(verb_session['id']))
                user = await db.scalar(select(User))
                user.selected_deck_id = session.deck_id
                user.selected_section_id = session.section_id
                user.selected_section_ids = session.section_ids
                user.direction = 'forward'
                user.input_mode = 'typing'
                user.selection_mode = 'random'
                # Also verify a previously unaffected learner and one without normal history.
                untouched = User(email='untouched@example.com', password_hash='unused',
                                 display_name='Untouched', selected_deck_id=first.id)
                no_history = User(email='no-history@example.com', password_hash='unused',
                                  display_name='No history', selected_deck_id=session.deck_id)
                db.add_all([untouched, no_history])
                await db.commit()
                content_before = list((await db.scalars(select(Card.id))).all())
                connection = await db.connection()
                await connection.run_sync(run_repair)
                await db.commit()
                await db.refresh(user)
                await db.refresh(untouched)
                await db.refresh(no_history)
                assert str(user.selected_deck_id) == expected['selected_deck_id']
                assert user.selected_section_ids == selected
                assert user.selected_section_id is None
                assert (user.direction, user.input_mode, user.selection_mode) == (
                    'mixed', 'reveal', 'adaptive',
                )
                assert untouched.selected_deck_id == first.id
                assert no_history.selected_deck_id == first.id
                assert no_history.selected_section_id is None
                assert no_history.selected_section_ids is None
                assert list((await db.scalars(select(Card.id))).all()) == content_before
