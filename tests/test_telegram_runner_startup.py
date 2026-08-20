from telegram_bot_runner import _personal_welcome


def test_personal_welcome_uses_first_name():
    text = _personal_welcome("Дмитрий")
    assert "Привет, Дмитрий!" in text
    assert "Мама, тут дешевле!" in text
    assert "Могу сама искать" in text
