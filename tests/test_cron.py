from datetime import datetime

from core import cron


def test_check_cron_value():
    dt = datetime(2016, 10, 5, 15, 20, 2)

    assert cron.check_cron_value('* * * * *', dt)
    assert cron.check_cron_value('18,20 * * * *', dt)
    assert cron.check_cron_value('18-20 * * * *', dt)
    assert cron.check_cron_value('20 15 * * *', dt)
    assert cron.check_cron_value('* * * * 3', dt)
    assert cron.check_cron_value('* * 5 * 3', dt)
    assert cron.check_cron_value('* * * 10 3', dt)
    assert cron.check_cron_value('* * * 10 1-5', dt)
    assert cron.check_cron_value('*/5 * * * *', dt)
    assert cron.check_cron_value('*/2 * * * *', dt)

    assert cron.check_cron_value('18,19 * * * *', dt) is False
    assert cron.check_cron_value('18-19 * * * *', dt) is False
    assert cron.check_cron_value('20 16 * * *', dt) is False
    assert cron.check_cron_value('* * * * 2', dt) is False
    assert cron.check_cron_value('* * 6 * 3', dt) is False
    assert cron.check_cron_value('* * * 10 4', dt) is False
    assert cron.check_cron_value('* * * 10 1-2', dt) is False
    assert cron.check_cron_value('*/3 * * * *', dt) is False
    assert cron.check_cron_value('*/8 * * * *', dt) is False

    assert cron.check_cron_values(('20 15 * * 1-5', '0 10 * * 6,7'), dt)
    assert cron.check_cron_values(('20 0 * * 1-5', '20 15 * * 6,7'), dt) is False
