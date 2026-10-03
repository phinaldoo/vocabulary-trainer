"""Small published catalogue shared by learner workflow integration tests."""

from app.models import Card, Deck, Section


async def make_deck(app, slug="learner-features", count=6):
    async with app.state.session_factory() as db:
        from sqlalchemy import func, select

        order = (await db.scalar(select(func.max(Deck.sort_order))) or 0) + 1
        deck = Deck(
            slug=slug,
            title=slug,
            front_label="Latin",
            back_label="German",
            front_language="la",
            back_language="de",
            status="published",
            sort_order=order,
        )
        db.add(deck)
        await db.flush()
        sections = [
            Section(deck_id=deck.id, stable_key=str(i), title=f"Chapter {i}", sort_order=i)
            for i in range(1, 4)
        ]
        db.add_all(sections)
        await db.flush()
        cards = [
            Card(
                deck_id=deck.id,
                section_id=sections[i % 3].id,
                stable_key=f"word-{i}",
                sort_order=i + 1,
                front_text=f"word-{count - i}",
                back_text=f"answer-{i}",
                details={
                    "gender": "f" if i % 2 else "m",
                    "part_of_speech": "noun",
                    "additional_info": f"note-{i}",
                    "additional_info_2": f"example-{i}",
                },
            )
            for i in range(count)
        ]
        db.add_all(cards)
        await db.commit()
        return deck, sections, cards
