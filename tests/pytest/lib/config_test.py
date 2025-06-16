# -*- coding: utf-8 -*-

import io

import pytest

from pyknic.lib.config import ConfigStorageProto, Config, ConfigList, ConfigOption

from pyknic.lib.capability import CapabilitiesHolder, iscapable


class TestConfigStorageProto:

    def test(self) -> None:
        storage = ConfigStorageProto()
        assert(isinstance(storage, CapabilitiesHolder))

    def test_exceptions(self) -> None:
        storage = ConfigStorageProto()

        with pytest.raises(NotImplementedError):
            assert(iscapable(storage, ConfigStorageProto.getitem) is False)
            storage[1]

        assert(iscapable(storage, ConfigStorageProto.as_int) is False)
        assert(iscapable(storage, ConfigStorageProto.as_float) is False)
        assert(iscapable(storage, ConfigStorageProto.as_bool) is False)
        assert(iscapable(storage, ConfigStorageProto.as_str) is False)
        for c in (int, float, bool, str):
            with pytest.raises(NotImplementedError):
                c(storage)

        for m in (
                ConfigStorageProto.is_none,
                ConfigStorageProto.properties,
                ConfigStorageProto.reset_properties,
                ConfigStorageProto.iterate_list
        ):
            with pytest.raises(NotImplementedError):
                assert(iscapable(storage, m) is False)
                m(storage)

        for m in (ConfigStorageProto.has_property, ConfigStorageProto.property):  # type: ignore[assignment]
            with pytest.raises(NotImplementedError):
                assert(iscapable(storage, m) is False)
                m(storage, 'foo')   # type: ignore[call-arg]

        with pytest.raises(NotImplementedError):
            assert(iscapable(storage, ConfigStorageProto.merge_file) is False)
            config_file = io.StringIO("")
            storage.merge_file(config_file)

        with pytest.raises(NotImplementedError):
            assert(iscapable(storage, ConfigStorageProto.merge_config) is False)
            storage.merge_config("")  # type: ignore[arg-type]


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
  null_val:
  str_val: foo

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
        assert(isinstance(config, ConfigStorageProto))

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
        config.reset_properties()
        assert(config.properties() == set())

    def test_section(self) -> None:
        config_file = io.StringIO(TestConfig.sample_config)
        config = Config(file_obj=config_file)

        section = config['big_section']
        assert(isinstance(section, Config))
        assert(section.has_property('general_int') is True)
        assert(section.has_property('prefix') is True)
        assert(section.has_property('int_value') is False)
        assert(section.has_property('float_value') is False)

        section = config.property('big_section')
        assert(isinstance(section, Config))
        assert(section.has_property('general_int') is True)
        assert(section.has_property('prefix') is True)
        assert(section.has_property('int_value') is False)
        assert(section.has_property('float_value') is False)

        sub_section = section['prefix']
        assert(isinstance(sub_section, Config))
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

        with pytest.raises(TypeError):
            config[0]

        with pytest.raises(ValueError):
            config.property('unknown_section')

        with pytest.raises(ValueError):
            config['unknown_section']

        extra_file = io.StringIO(TestConfig.extra_config)
        extra_config = Config(file_obj=extra_file)

        with pytest.raises(ValueError):
            config.merge_config(extra_config, 'unknown_section')

        with pytest.raises(TypeError):
            config.merge_config(ConfigList())


class TestConfigList:

    def test(self) -> None:
        config_file = io.StringIO(TestConfig.sample_config)
        config = Config(file_obj=config_file)

        config_list = config['section4']
        assert(isinstance(config_list, ConfigList))
        assert(isinstance(config_list, ConfigStorageProto))

        config_list_items = list(config_list.iterate_list())
        assert(len(config_list_items) == 4)

        assert(isinstance(config_list[0], ConfigOption))
        assert(config_list[0].is_none() is False)
        assert(int(config_list[0]) == 1)

        assert(isinstance(config_list[1], ConfigOption))
        assert(config_list[1].is_none() is True)

        assert(isinstance(config_list[2], ConfigOption))
        assert(config_list[2].is_none() is False)
        assert(str(config_list[2]) == "foo")

        assert(isinstance(config_list[3], ConfigOption) is False)
        assert(isinstance(config_list[3], Config))
        assert(config_list[3].properties() == {"foo", })
        assert([str(x) for x in config_list[3]["foo"].iterate_list()] == ["xxx", "yyy", "zzz"])


class TestConfigOption:

    def test(self) -> None:
        config_file = io.StringIO(TestConfig.sample_config)
        config = Config(file_obj=config_file)

        option = config['section1']['integer_option']
        assert(isinstance(option, ConfigOption))
        assert(isinstance(option, ConfigStorageProto))
        pytest.raises(TypeError, str, option)
        assert(int(option) == 1)

        assert(float(config['section2']['float_option']) == 0.5)
        assert(bool(config['big_section']['boolean_value']) is True)
        assert(bool(config['big_section']['yes_val']) is False)
        assert(config['big_section']['null_val'].is_none())
        assert(str(config['big_section']['str_val']) == 'foo')
