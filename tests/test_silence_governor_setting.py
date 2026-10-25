import pytest

from heartbeat2 import governor
from heartbeat2.policy import Policy
from test_engine import arm, engine


def test_opt_out_disables_noop_pause_but_keeps_slowdown(engine):
    wake = arm(engine, 'every', noop_streak=6)
    engine.policy = Policy.from_settings({'silence_governor_enabled': False}, clock=engine.clock)

    governor.apply(engine, wake)

    current = engine.store.get_wake(wake.id)
    assert current.status == 'active'
    assert current.eff_interval_s > current.base_interval_s


def test_opt_out_disables_ratio_pause_for_silent_notifications(engine):
    wake = arm(engine, 'every')
    engine.policy = Policy.from_settings({'silence_governor_enabled': False}, clock=engine.clock)
    for i in range(12):
        key = f't:ratio-{i}'
        engine.store.add_occurrence(wake.id, key)
        assert engine.store.claim(wake.id, key, epoch='test', pid=1)
        assert engine.store.start(wake.id, key, attempt=1)
        assert engine.store.finish(wake.id, key, attempt=1, outcome='progress', notify=False)

    governor.apply(engine, wake)

    assert engine.store.get_wake(wake.id).status == 'active'


def test_opt_out_keeps_ignored_and_error_pauses(engine):
    ignored = arm(engine, 'every', ignored_streak=3)
    engine.policy = Policy.from_settings({'silence_governor_enabled': False}, clock=engine.clock)
    governor.apply(engine, ignored)
    assert engine.store.get_wake(ignored.id).status_reason == 'governor:ignored'

    failed = arm(engine, 'every')
    for _ in range(engine.policy.error_pause_after):
        governor.error(engine, engine.store.get_wake(failed.id))
    assert engine.store.get_wake(failed.id).status_reason == 'governor:error'


@pytest.mark.parametrize('value,expected', [(False, False), ('false', False), ('0', False),
                                            (True, True), ('true', True), ('1', True)])
def test_setting_parses_boolean(value, expected, clock):
    policy = Policy.from_settings({'silence_governor_enabled': value}, clock=clock)
    assert policy.silence_governor_enabled is expected


def test_setting_defaults_on_and_is_exposed_in_plugin_schema(clock):
    import yaml
    from pathlib import Path

    assert Policy.from_settings({}, clock=clock).silence_governor_enabled is True
    root = Path(__file__).resolve().parents[1]
    schema = yaml.safe_load((root / 'plugin.yaml').read_text())['config_schema']
    assert schema['silence_governor_enabled']['type'] == 'bool'
    assert schema['silence_governor_enabled']['default'] is True


def test_setting_rejects_invalid_boolean(clock):
    with pytest.raises(ValueError, match='silence_governor_enabled'):
        Policy.from_settings({'silence_governor_enabled': 'sometimes'}, clock=clock)
