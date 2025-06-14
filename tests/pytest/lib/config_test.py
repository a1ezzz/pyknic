# -*- coding: utf-8 -*-

import io
import pytest

from pyknic.lib.config import Config, ConfigList, ConfigOption, _ConfigImplementation, _cast_implementation


class TestConfig:

    sample_config = """
section1:
  integer_option: 1

section2:
  float_option: 0.5

section3:
  emoji = 😃

section4:
  - 1
  -
  - foo
  - foo:
    - xxx
    - yyy
    - zzz

big_section:
  general_int: 0
  boolean_value: True
  yes_val: no

  prefix:
    int_value: 1
    float_value: 1.2

"""

    extra_config = """
section1:
  integer_option: 2

section5:
  value: foo
"""

    def test_plain(self) -> None:
        config_file = io.StringIO(TestConfig.sample_config)

        config = Config()
        assert(config.properties() == set())

        config = Config(file_obj=config_file)
        assert(config.properties() == {"section1", "section2", "section3", "section4", "big_section"})

        config_file.seek(0)
        config = Config(file_obj=config_file, property_name="section1")
        assert(config.properties() == {"section1", })

    def test_sections(self) -> None:
        config_file = io.StringIO(TestConfig.sample_config)
        config = Config(file_obj=config_file)
        assert(config.properties() == {"section1", "section2", "section3", "section4", "big_section"})
        assert(config.has_property("section1") is True)
        assert(config.has_property("section5") is False)

    def test_reset(self) -> None:
        config_file = io.StringIO(TestConfig.sample_config)
        config = Config(file_obj=config_file)
        assert(config.properties() == {"section1", "section2", "section3", "section4", "big_section"})
        config.reset()
        assert(config.properties() == set())

    def test_section(self) -> None:
        config_file = io.StringIO(TestConfig.sample_config)
        config = Config(file_obj=config_file)

        section = config['big_section']
        assert(isinstance(section, Config) is True)
        assert(section.has_property('general_int') is True)
        assert(section.has_property('prefix') is True)
        assert(section.has_property('int_value') is False)
        assert(section.has_property('float_value') is False)

        section = config.property('big_section')
        assert(isinstance(section, Config) is True)
        assert(section.has_property('general_int') is True)
        assert(section.has_property('prefix') is True)
        assert(section.has_property('int_value') is False)
        assert(section.has_property('float_value') is False)

        sub_section = section['prefix']
        assert(isinstance(sub_section, Config) is True)
        assert(sub_section.has_property('general_int') is False)
        assert(sub_section.has_property('prefix') is False)
        assert(sub_section.has_property('int_value') is True)
        assert(sub_section.has_property('float_value') is True)

    def test_merge_file(self) -> None:
        config_file = io.StringIO(TestConfig.sample_config)
        config = Config(file_obj=config_file)
        assert(config.has_property('section5') is False)
        assert(int(config['section1']['integer_option']) == 1)

        extra_file = io.StringIO(TestConfig.extra_config)
        config.merge_file(extra_file)
        assert(config.has_property('section5') is True)
        assert(int(config['section1']['integer_option']) == 2)

    def test_config_merge(self) -> None:
        config_file = io.StringIO(TestConfig.sample_config)
        config = Config(file_obj=config_file)
        assert(config.has_property('section5') is False)
        assert(int(config['section1']['integer_option']) == 1)

        extra_file = io.StringIO(TestConfig.extra_config)
        extra_config = Config(file_obj=extra_file)
        config.merge_config(extra_config)
        assert(config.has_property('section5') is True)
        assert(int(config['section1']['integer_option']) == 2)

    def test_partial_config_merge(self) -> None:
        config_file = io.StringIO(TestConfig.sample_config)
        config = Config(file_obj=config_file)

        extra_file = io.StringIO(TestConfig.extra_config)
        extra_config = Config(file_obj=extra_file)
        config.merge_config(extra_config, property_name='section1')

        assert(config.has_property('section5') is False)
        assert(int(config['section1']['integer_option']) == 2)

    def test_exceptions(self) -> None:
        config_file = io.StringIO(TestConfig.sample_config)
        config = Config(file_obj=config_file)

        with pytest.raises(ValueError):
            config.property('unknown_section')

        with pytest.raises(ValueError):
            config['unknown_section']

        extra_file = io.StringIO(TestConfig.extra_config)
        extra_config = Config(file_obj=extra_file)

        with pytest.raises(ValueError):
            config.merge_config(extra_config, 'unknown_section')

        with pytest.raises(TypeError):
            config.merge_config(_cast_implementation(_ConfigImplementation([])))

    def test_list(self):
        config_file = io.StringIO(TestConfig.sample_config)
        config = Config(file_obj=config_file)

        config_list = config['section4']
        assert(isinstance(config_list, ConfigList) is True)

        config_list_items = list(config_list.iterate())
        assert(len(config_list_items) == 4)

        assert(isinstance(config_list[0], ConfigOption) is True)
        assert(config_list[0].option_type() is int)
        assert(config_list[0].is_none() is False)
        assert(int(config_list[0]) == 1)

        assert(isinstance(config_list[1], ConfigOption) is True)
        assert(config_list[1].option_type() is None)
        assert(config_list[1].is_none() is True)

        assert(isinstance(config_list[2], ConfigOption) is True)
        assert(config_list[2].option_type() is str)
        assert(config_list[2].is_none() is False)
        assert(str(config_list[2]) == "foo")

        assert(isinstance(config_list[3], ConfigOption) is False)
        assert(isinstance(config_list[3], Config) is True)
        assert(config_list[3].properties() == {"foo", })
        assert([str(x) for x in config_list[3]["foo"].iterate()] == ["xxx", "yyy", "zzz"])


class TestConfigOption:

    def test(self) -> None:
        config_file = io.StringIO(TestConfig.sample_config)
        config = Config(file_obj=config_file)

        option = config['section1']['integer_option']
        assert(isinstance(option, ConfigOption) is True)
        pytest.raises(TypeError, str, option)
        assert(int(option) == 1)

        assert(float(config['section2']['float_option']) == 0.5)
        assert(bool(config['big_section']['boolean_value']) is True)
        assert(bool(config['big_section']['yes_val']) is False)
