from telegram_bot import _rerun_deal_action


def test_deal_action_module_imports_context_resolver():
    # Regression guard: deal actions must resolve against the active conversation.
    import telegram_bot as bot
    from search_context import resolve_search_query

    assert bot.resolve_search_query is resolve_search_query
    assert callable(_rerun_deal_action)
