# -*- coding: utf-8 -*-

import io
import pytest

from pyknic.lib.config import Config, ConfigSection, ConfigOption, AppConfig


class TestConfig:

    sample_config = """
[section1]
integer_option = 1

[section2]
float_option: 0.5

[section3]
emoji = 😃

[big_section]
general_int = 0
prefix1_int = 1
prefix1_float = 1.2
boolean_value = True
yes_val = no
"""

    extra_config = """
[section1]
integer_option = 2

[section4]
value = foo
"""

    def test_plain(self) -> None:
        config_file = io.StringIO(TestConfig.sample_config)

        config = Config()
        assert(config.sections() == set())

        config = Config(config_file)
        assert(config.sections() == {"section1", "section2", "section3", "big_section"})

        config_file.seek(0)
        config = Config(config_file, section="section1")
        assert(config.sections() == {"section1", })

    def test_sections(self) -> None:
        config_file = io.StringIO(TestConfig.sample_config)
        config = Config(config_file)
        assert(config.sections() == {"section1", "section2", "section3", "big_section"})
        assert(config.has_section("section1") is True)
        assert(config.has_section("section4") is False)

    def test_options(self) -> None:
        config_file = io.StringIO(TestConfig.sample_config)
        config = Config(config_file)
        assert(config.has_option('section1', 'integer_option') is True)
        assert(config.has_option('section1', 'float_option') is False)
        assert(config.has_option('section4', 'float_option') is False)

    def test_reset(self) -> None:
        config_file = io.StringIO(TestConfig.sample_config)
        config = Config(config_file)
        assert(config.sections() == {"section1", "section2", "section3", "big_section"})
        config.reset()
        assert(config.sections() == set())

    def test_section(self) -> None:
        config_file = io.StringIO(TestConfig.sample_config)
        config = Config(config_file)

        section = config['big_section']
        assert(isinstance(section, ConfigSection) is True)
        assert(section.has_option('general_int') is True)
        assert(section.has_option('prefix1_int') is True)
        assert(section.has_option('prefix1_float') is True)
        assert(section.has_option('int') is False)
        assert(section.has_option('float') is False)

        section = config.section('big_section')
        assert(isinstance(section, ConfigSection) is True)
        assert(section.has_option('general_int') is True)
        assert(section.has_option('prefix1_int') is True)
        assert(section.has_option('prefix1_float') is True)
        assert(section.has_option('int') is False)
        assert(section.has_option('float') is False)

        section = config.section('big_section', option_prefix='prefix1_')
        assert(isinstance(section, ConfigSection) is True)
        assert(section.has_option('general_int') is False)
        assert(section.has_option('prefix1_int') is False)
        assert(section.has_option('prefix1_float') is False)
        assert(section.has_option('int') is True)
        assert(section.has_option('float') is True)

    def test_merge_file(self) -> None:
        config_file = io.StringIO(TestConfig.sample_config)
        config = Config(config_file)
        assert(config.has_section('section4') is False)
        assert(int(config['section1']['integer_option']) == 1)

        extra_file = io.StringIO(TestConfig.extra_config)
        config.merge_file(extra_file)
        assert(config.has_section('section4') is True)
        assert(int(config['section1']['integer_option']) == 2)

    def test_config_merge(self) -> None:
        config_file = io.StringIO(TestConfig.sample_config)
        config = Config(config_file)
        assert(config.has_section('section4') is False)
        assert(int(config['section1']['integer_option']) == 1)

        extra_file = io.StringIO(TestConfig.extra_config)
        extra_config = Config(extra_file)
        config.merge_config(extra_config)
        assert(config.has_section('section4') is True)
        assert(int(config['section1']['integer_option']) == 2)

    def test_partial_config_merge(self) -> None:
        config_file = io.StringIO(TestConfig.sample_config)
        config = Config(config_file)

        extra_file = io.StringIO(TestConfig.extra_config)
        extra_config = Config(extra_file)
        config.merge_config(extra_config, section='section1')

        assert(config.has_section('section4') is False)
        assert(int(config['section1']['integer_option']) == 2)

    def test_subsection(self) -> None:
        config_file = io.StringIO(TestConfig.sample_config)
        config = Config(config_file)
        assert(config.sections() == {"section1", "section2", "section3", "big_section"})

        config_subset = config.sections_subset('section')
        assert(config_subset.sections() == {"section1", "section2", "section3"})

        extra_file = io.StringIO(TestConfig.extra_config)
        extra_config = Config(extra_file)
        config_subset.merge_config(extra_config)

        assert(config.has_section('section4') is False)
        assert(config_subset.has_section('section4') is True)

    def test_exceptions(self) -> None:
        config_file = io.StringIO(TestConfig.sample_config)
        config = Config(config_file)

        with pytest.raises(ValueError):
            config.section('unknown_section')

        with pytest.raises(ValueError):
            config['unknown_section']

        extra_file = io.StringIO(TestConfig.extra_config)
        extra_config = Config(extra_file)

        with pytest.raises(ValueError):
            config.merge_config(extra_config, 'unknown_section')


class TestConfigSection:

    def test(self) -> None:
        config_file = io.StringIO(TestConfig.sample_config)
        config = Config(config_file)

        config_section = config.section('big_section', option_prefix='prefix1_')
        assert(isinstance(config_section, ConfigSection) is True)
        assert(config_section.config() is config)
        assert(config_section.section() == 'big_section')
        assert(config_section.options_prefix() == 'prefix1_')
        assert(config_section.has_option('general_int') is False)
        assert(config_section.has_option('prefix1_int') is False)
        assert(config_section.has_option('int') is True)

        config_section = config.section('big_section')
        assert(config_section.config() is config)
        assert(config_section.section() == 'big_section')
        assert(config_section.options_prefix() is None)
        assert(config_section.has_option('general_int') is True)
        assert(config_section.has_option('prefix1_int') is True)
        assert(config_section.has_option('int') is False)


class TestConfigOption:

    def test(self) -> None:
        config_file = io.StringIO(TestConfig.sample_config)
        config = Config(config_file)

        option = config['section1']['integer_option']
        assert(isinstance(option, ConfigOption) is True)
        assert(str(option) == '1')
        assert(option.config() is config)
        assert(option.section() == 'section1')
        assert(option.option() == 'integer_option')

        assert(float(config['section2']['float_option']) == 0.5)
        assert(bool(config['big_section']['boolean_value']) is True)
        assert(bool(config['big_section']['yes_val']) is False)


def test_config() -> None:
    assert(isinstance(AppConfig, Config) is True)
    assert(AppConfig.sections() == set())
