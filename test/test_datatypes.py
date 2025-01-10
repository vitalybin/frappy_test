# *****************************************************************************
#
# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation; either version 2 of the License, or (at your option) any later
# version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc.,
# 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#
# Module authors:
#   Enrico Faulhaber <enrico.faulhaber@frm2.tum.de>
#
# *****************************************************************************
"""test data types."""


# no fixtures needed
import pytest

from frappy.datatypes import ArrayOf, BLOBType, BoolType, CommandType, \
    ConfigError, DataType, EnumType, FloatRange, \
    IntRange, ProgrammingError, ScaledInteger, StatusType, StringType, \
    StructOf, TextType, TupleOf, ValueType, get_datatype
from frappy.errors import BadValueError, RangeError, WrongTypeError
from frappy.lib import generalConfig


def copytest(dt):
    assert repr(dt) == repr(dt.copy())
    assert dt.export_datatype() == dt.copy().export_datatype()
    assert dt != dt.copy()


def test_DataType():
    dt = DataType()
    with pytest.raises(ProgrammingError):
        dt.export_datatype()
    with pytest.raises(NotImplementedError):
        dt('')
    dt.export_value('')


def test_FloatRange():
    dt = FloatRange(-3.14, 3.14)
    copytest(dt)
    assert dt.export_datatype() == {'type': 'double', 'min':-3.14, 'max':3.14}

    with pytest.raises(RangeError):
        dt.validate(9)
    with pytest.raises(RangeError):
        dt.validate(-9)
    dt(9)  # convert, but do not check limits
    dt(-9)  # convert, but do not check limits
    with pytest.raises(WrongTypeError):
        dt('XX')
    with pytest.raises(WrongTypeError):
        dt.import_value('XX')
    with pytest.raises(WrongTypeError):
        dt([19, 'X'])
    with pytest.raises(WrongTypeError):
        dt.import_value([19, 'X'])
    dt(1)
    dt(0)
    dt(13.14 - 10)  # raises an error, if resolution is not handled correctly
    assert dt.export_value(-2.718) == -2.718
    assert dt.import_value(-2.718) == -2.718
    with pytest.raises(ProgrammingError):
        FloatRange('x', 'Y')
    # check that unit can be changed
    dt.setProperty('unit', 'K')
    assert dt.export_datatype() == {'type': 'double', 'min':-3.14, 'max':3.14, 'unit': 'K'}
    with pytest.raises(KeyError):
        dt.setProperty('visibility', 0)
    dt.setProperty('absolute_resolution', 0)

    dt = FloatRange()
    copytest(dt)
    assert dt.export_datatype() == {'type': 'double'}

    dt = FloatRange(unit='X', fmtstr='%.2f', absolute_resolution=1,
                    relative_resolution=0.1)
    copytest(dt)
    assert dt.export_datatype() == {'type': 'double', 'unit':'X', 'fmtstr':'%.2f',
                                      'absolute_resolution':1.0,
                                      'relative_resolution':0.1}
    assert dt(4) == 4
    assert dt.format_value(3.14) == '3.14 X'
    assert dt.format_value(3.14, '') == '3.14'
    assert dt.format_value(3.14, '#') == '3.14 #'

    dt.setProperty('min', 1)
    dt.setProperty('max', 0)
    with pytest.raises(ConfigError):
        dt.checkProperties()

    with pytest.raises(ProgrammingError):
        FloatRange(resolution=1)


def test_IntRange():
    dt = IntRange(-3, 3)
    copytest(dt)
    assert dt.export_datatype() == {'type': 'int', 'min':-3, 'max':3}

    with pytest.raises(RangeError):
        dt.validate(9)
    with pytest.raises(RangeError):
        dt.validate(-9)
    dt(9)  # convert, but do not check limits
    dt(-9)  # convert, but do not check limits
    with pytest.raises(WrongTypeError):
        dt('XX')
    with pytest.raises(WrongTypeError):
        dt.import_value('XX')
    with pytest.raises(WrongTypeError):
        dt([19, 'X'])
    with pytest.raises(WrongTypeError):
        dt.import_value([19, 'X'])
    with pytest.raises(WrongTypeError):
        dt(1.3)
    with pytest.raises(WrongTypeError):
        dt.import_value(1.3)
    with pytest.raises(WrongTypeError):
        dt('1.3')
    with pytest.raises(WrongTypeError):
        dt.import_value('1.3')
    dt(1)
    dt(0)
    with pytest.raises(ProgrammingError):
        IntRange('xc', 'Yx')

    dt = IntRange()
    copytest(dt)
    assert dt.export_datatype()['type'] == 'int'
    assert dt.export_datatype()['min'] < 0 < dt.export_datatype()['max']
    assert dt.export_datatype() == {'type': 'int', 'max': 16777216,'min': -16777216}
    assert dt.format_value(42) == '42'

    dt.setProperty('min', 1)
    dt.setProperty('max', 0)
    with pytest.raises(ConfigError):
        dt.checkProperties()


def test_ScaledInteger():
    dt = ScaledInteger(0.01, -3, 3)
    copytest(dt)
    # serialisation of datatype contains limits on the 'integer' value
    assert dt.export_datatype() == {'type': 'scaled', 'scale':0.01, 'min':-300, 'max':300}

    with pytest.raises(RangeError):
        dt.validate(9)
    with pytest.raises(RangeError):
        dt.validate(-9)
    dt(9)  # convert, but do not check limits
    dt(-9)  # convert, but do not check limits
    with pytest.raises(WrongTypeError):
        dt('XX')
    with pytest.raises(WrongTypeError):
        dt.import_value('XX')
    with pytest.raises(WrongTypeError):
        dt([19, 'X'])
    with pytest.raises(WrongTypeError):
        dt.import_value([19, 'X'])
    dt(1)
    dt(0)
    with pytest.raises(ProgrammingError):
        ScaledInteger('xc', 'Yx')
    with pytest.raises(ProgrammingError):
        ScaledInteger(scale=0, min=1, max=2)
    with pytest.raises(ProgrammingError):
        ScaledInteger(scale=-10, min=1, max=2)
    # check that unit can be changed
    dt.setProperty('unit', 'A')
    assert dt.export_datatype() == {'type': 'scaled', 'scale':0.01, 'min':-300, 'max':300,
                                    'unit': 'A'}

    assert dt.export_value(0.0001) == int(0)
    assert dt.export_value(2.71819) == int(272)
    assert dt.import_value(272) == 2.72

    dt.setProperty('scale', 0.1)
    assert dt.export_datatype() == {'type': 'scaled', 'scale':0.1, 'min':-30, 'max':30,
                                    'unit':'A'}
    assert dt.absolute_resolution == dt.scale

    dt = ScaledInteger(0.003, 0.4, 1, unit='X', fmtstr='%.1f',
                       absolute_resolution=0.001, relative_resolution=1e-5)
    copytest(dt)
    assert dt.export_datatype() == {'type': 'scaled', 'scale':0.003, 'min':133, 'max':333,
                                      'unit':'X', 'fmtstr':'%.1f',
                                      'absolute_resolution':0.001,
                                      'relative_resolution':1e-5}
    assert round(dt(0.7), 5) == 0.699
    assert dt.format_value(0.6) == '0.6 X'
    assert dt.format_value(0.6, '') == '0.6'
    assert dt.format_value(0.6, 'Z') == '0.6 Z'
    assert round(dt.validate(1.0004), 5) == 0.999  # rounded value within limit
    with pytest.raises(RangeError):
        dt.validate(1.006)  # rounded value outside limit
    assert round(dt.validate(0.398), 5) == 0.399  # rounded value within rounded limit
    with pytest.raises(RangeError):
        dt.validate(0.395)  # rounded value outside limit

    dt.setProperty('min', 1)
    dt.setProperty('max', 0)
    with pytest.raises(ConfigError):
        dt.checkProperties()

    with pytest.raises(WrongTypeError):
        dt.setProperty('scale', None)


def test_EnumType():
    # test constructor catching illegal arguments
    with pytest.raises(TypeError):
        EnumType(1)
    with pytest.raises(TypeError):
        EnumType(['b', 0])

    dt = EnumType('dt', a=3, c=7, stuff=1)
    copytest(dt)

    assert dt.export_datatype() == {'type': 'enum', 'members': {'a': 3, 'c': 7, 'stuff': 1}}

    with pytest.raises(RangeError):
        dt(9)
    with pytest.raises(RangeError):
        dt.import_value(9)
    with pytest.raises(RangeError):
        dt(-9)
    with pytest.raises(RangeError):
        dt.import_value(-9)
    with pytest.raises(RangeError):
        dt('XX')
    with pytest.raises(RangeError):
        dt.import_value('XX')
    with pytest.raises(WrongTypeError):
        dt([19, 'X'])
    with pytest.raises(WrongTypeError):
        dt.import_value([19, 'X'])

    assert dt('a') == 3
    assert dt('stuff') == 1
    assert dt(1) == 1
    with pytest.raises(RangeError):
        dt(2)

    assert dt.export_value('c') == 7
    assert dt.export_value('stuff') == 1
    assert dt.export_value(1) == 1
    assert dt.import_value('c') == 7
    assert dt.import_value('a') == 3
    assert dt.import_value('stuff') == 1
    with pytest.raises(RangeError):
        dt.export_value(2)
    with pytest.raises(RangeError):
        dt.import_value('A')

    assert dt.format_value(3) == 'a<3>'


def test_BLOBType():
    # test constructor catching illegal arguments
    dt = BLOBType()
    copytest(dt)
    assert dt.export_datatype() == {'type': 'blob', 'maxbytes':255}
    dt = BLOBType(10)
    copytest(dt)
    assert dt.export_datatype() == {'type': 'blob', 'minbytes':10, 'maxbytes':10}

    dt = BLOBType(3, 10)
    copytest(dt)
    assert dt.export_datatype() == {'type': 'blob', 'minbytes':3, 'maxbytes':10}

    with pytest.raises(WrongTypeError):
        dt(9)
    with pytest.raises(RangeError):
        dt(b'av')
    with pytest.raises(RangeError):
        dt(b'abcdefghijklmno')
    with pytest.raises(WrongTypeError):
        dt('abcd')
    with pytest.raises(WrongTypeError):
        dt.import_value('ab')
    with pytest.raises(WrongTypeError):
        dt.import_value(b'xxx')
    assert dt(b'abcd') == b'abcd'

    dt.setProperty('minbytes', 1)
    dt.setProperty('maxbytes', 0)
    with pytest.raises(ConfigError):
        dt.checkProperties()

    assert dt.export_value(b'abcd') == 'YWJjZA=='
    assert dt.export_value(b'abcd') == 'YWJjZA=='
    # assert dt.export_value('abcd') == 'YWJjZA=='
    assert dt.import_value('YWJjZA==') == b'abcd'

    # XXX: right? or different format?
    # to be added after migration to py3
    # assert dt.format_value(b'ab\0cd') == "b'ab\\x00cd\'"


def test_StringType():
    # test constructor catching illegal arguments
    dt = StringType()
    copytest(dt)
    assert dt.export_datatype() == {'type': 'string'}
    dt = StringType(12)
    copytest(dt)
    assert dt.export_datatype() == {'type': 'string', 'minchars':12, 'maxchars':12}

    dt = StringType(4, 11)
    copytest(dt)
    assert dt.export_datatype() == {'type': 'string', 'minchars':4, 'maxchars':11}

    with pytest.raises(WrongTypeError):
        dt(9)
    with pytest.raises(RangeError):
        dt('av')
    with pytest.raises(RangeError):
        dt('abcdefghijklmno')
    with pytest.raises(RangeError):
        dt('abcdefg\0')
    assert dt('abcd') == 'abcd'
    # tests with bytes have to be added after migration to py3
    #assert dt(b'abcd') == 'abcd'

    assert dt.export_value('abcd') == 'abcd'
    # assert dt.export_value(b'abcd') == 'abcd'
    assert dt.import_value('abcd') == 'abcd'

    assert dt.format_value('abcd') == "'abcd'"

    dt.setProperty('minchars', 1)
    dt.setProperty('maxchars', 0)
    with pytest.raises(ConfigError):
        dt.checkProperties()


def test_TextType():
    # test constructor catching illegal arguments
    dt = TextType(12)
    copytest(dt)
    assert dt.export_datatype() == {'type': 'string', 'maxchars':12}

    with pytest.raises(WrongTypeError):
        dt(9)
    with pytest.raises(RangeError):
        dt('abcdefghijklmno')
    with pytest.raises(RangeError):
        dt('abcdefg\0')
    assert dt('ab\n\ncd\n') == 'ab\n\ncd\n'
    # assert dt(b'ab\n\ncd\n') == 'ab\n\ncd\n'

    assert dt.export_value('abcd') == 'abcd'
    # assert dt.export_value(b'abcd') == b'abcd'
    assert dt.export_value('abcd') == 'abcd'
    assert dt.import_value('abcd') == 'abcd'


def test_BoolType():
    # test constructor catching illegal arguments
    dt = BoolType()
    copytest(dt)
    assert dt.export_datatype() == {'type': 'bool'}

    with pytest.raises(WrongTypeError):
        dt(9)
    with pytest.raises(WrongTypeError):
        dt('av')

    assert dt('true') is True
    assert dt('off') is False
    assert dt(1) is True

    assert dt.export_value('false') is False
    assert dt.export_value(0) is False
    assert dt.export_value('on') is True

    assert dt.import_value(False) is False
    assert dt.import_value(True) is True
    with pytest.raises(WrongTypeError):
        dt.import_value('av')

    assert dt.format_value(0) == "False"
    assert dt.format_value(True) == "True"

    with pytest.raises(TypeError):
        # pylint: disable=unexpected-keyword-arg
        BoolType(unit='K')


def test_ArrayOf():
    # test constructor catching illegal arguments
    with pytest.raises(ProgrammingError):
        ArrayOf(int)
    with pytest.raises(ProgrammingError):
        ArrayOf(-3, IntRange(-10,10))
    dt = ArrayOf(IntRange(-10, 10), 5)
    copytest(dt)
    assert dt.export_datatype() == {'type': 'array', 'minlen':5, 'maxlen':5,
                                     'members': {'type': 'int', 'min':-10,
                                                 'max':10}}

    dt = ArrayOf(FloatRange(-10, 10, unit='Z'), 1, 3)
    copytest(dt)
    assert dt.export_datatype() == {'type': 'array', 'minlen':1, 'maxlen':3,
                                     'members':{'type': 'double', 'min':-10,
                                                'max':10, 'unit': 'Z'}}
    with pytest.raises(WrongTypeError):
        dt(9)
    with pytest.raises(WrongTypeError):
        dt('av')

    assert dt([1, 2, 3]) == (1, 2, 3)

    assert dt.export_value([1, 2, 3]) == [1, 2, 3]
    assert dt.import_value([1, 2, 3]) == (1, 2, 3)

    assert dt.format_value([1,2,3]) == '[1, 2, 3] Z'
    assert dt.format_value([1,2,3], '') == '[1, 2, 3]'
    assert dt.format_value([1,2,3], 'Q') == '[1, 2, 3] Q'

    dt = ArrayOf(FloatRange(unit='K'))
    assert dt.members.unit == 'K'
    dt.setProperty('unit', 'mm')
    with pytest.raises(TypeError):
        # pylint: disable=unexpected-keyword-arg
        ArrayOf(BoolType(), unit='K')

    dt.setProperty('minlen', 1)
    dt.setProperty('maxlen', 0)
    with pytest.raises(ConfigError):
        dt.checkProperties()

    dt = ArrayOf(EnumType('myenum', single=0), 5)
    copytest(dt)

    dt = ArrayOf(ArrayOf(FloatRange(unit='m')))
    assert dt.format_value([[0, 1], [2, 3]]) == '[[0, 1], [2, 3]] m'


def test_TupleOf():
    # test constructor catching illegal arguments
    with pytest.raises(ProgrammingError):
        TupleOf(2)

    dt = TupleOf(IntRange(-10, 10), BoolType())
    copytest(dt)
    assert dt.export_datatype() == {'type': 'tuple',
       'members':[{'type': 'int', 'min':-10, 'max':10}, {'type': 'bool'}]}
    with pytest.raises(WrongTypeError):
        dt(9)
    with pytest.raises(WrongTypeError):
        dt([99, 'X'])

    assert dt([1, True]) == (1, True)

    assert dt.export_value([1, True]) == [1, True]
    assert dt.import_value([1, True]) == (1, True)

    assert dt.format_value([3,0]) == "(3, False)"

    dt = TupleOf(EnumType('myenum', single=0))
    copytest(dt)


def test_StructOf():
    # test constructor catching illegal arguments
    with pytest.raises(ProgrammingError):
        StructOf(IntRange)  # pylint: disable=E1121
    with pytest.raises(ProgrammingError):
        StructOf(IntRange=1)

    dt = StructOf(a_string=StringType(0, 55), an_int=IntRange(0, 999),
                  optional=['an_int'])
    copytest(dt)
    assert dt.export_datatype() == {'type': 'struct',
      'members':{'a_string': {'type': 'string', 'maxchars':55},
                 'an_int': {'type': 'int', 'min':0, 'max':999}},
      'optional':['an_int']}

    with pytest.raises(WrongTypeError):
        dt(9)
    with pytest.raises(WrongTypeError):
        dt([99, 'X'])
    with pytest.raises(RangeError):
        dt.validate({'a_string': 'XXX', 'an_int': 1811})

    assert dt({'a_string': 'XXX', 'an_int': 8}) == {'a_string': 'XXX',
                                                    'an_int': 8}
    assert dt.export_value({'an_int': 13, 'a_string': 'WFEC'}) == {
        'a_string': 'WFEC', 'an_int': 13}
    assert dt.import_value({'an_int': 13, 'a_string': 'WFEC'}) == {
        'a_string': 'WFEC', 'an_int': 13}

    assert dt.format_value({'an_int': 2, 'a_string': 'Z'}) == "{an_int=2, a_string='Z'}"

    dt = StructOf(['optionalmember'], optionalmember=EnumType('myenum', single=0))
    copytest(dt)


def test_Command():
    dt = CommandType()
    assert dt.export_datatype() == {'type': 'command'}

    dt = CommandType(IntRange(-1,1))
    assert dt.export_datatype() == {'type': 'command', 'argument':{'type': 'int', 'min':-1, 'max':1}}

    dt = CommandType(IntRange(-1,1), IntRange(-3,3))
    assert dt.export_datatype() == {'type': 'command',
        'argument':{'type': 'int', 'min':-1, 'max':1},
        'result':{'type': 'int', 'min':-3, 'max':3}}


def test_StatusType():
    dt = StatusType('IDLE', 'WARN', 'ERROR', 'DISABLED')
    assert dt.IDLE == StatusType.IDLE == 100
    assert dt.ERROR == StatusType.ERROR == 400

    dt2 = StatusType(None, IDLE=100, WARN=200, ERROR=400, DISABLED=0)
    assert dt2.export_datatype() == dt.export_datatype()

    dt3 = StatusType(dt.enum)
    assert dt3.export_datatype() == dt.export_datatype()

    with pytest.raises(ProgrammingError):
        StatusType('__init__')  # built in attribute of StatusType

    with pytest.raises(ProgrammingError):
        StatusType(dt.enum, 'custom')  # not a standard attribute

    StatusType(dt.enum, custom=499)  # o.k., if value is given


def test_get_datatype():
    with pytest.raises(WrongTypeError):
        get_datatype(1)
    with pytest.raises(WrongTypeError):
        get_datatype(True)
    with pytest.raises(WrongTypeError):
        get_datatype(str)
    with pytest.raises(WrongTypeError):
        get_datatype({'undefined': {}})

    assert isinstance(get_datatype({'type': 'bool'}), BoolType)
    with pytest.raises(WrongTypeError):
        get_datatype(['bool'])

    with pytest.raises(WrongTypeError):
        get_datatype({'type': 'int', 'min':-10}) # missing max
    with pytest.raises(WrongTypeError):
        get_datatype({'type': 'int', 'max':10}) # missing min
    assert isinstance(get_datatype({'type': 'int', 'min':-10, 'max':10}), IntRange)

    with pytest.raises(WrongTypeError):
        get_datatype({'type': 'int', 'min':10, 'max':-10}) # min > max
    with pytest.raises(WrongTypeError):
        get_datatype({'type': 'int'}) # missing limits
    with pytest.raises(WrongTypeError):
        get_datatype({'type': 'int', 'x': 2})

    assert isinstance(get_datatype({'type': 'double'}), FloatRange)
    assert isinstance(get_datatype({'type': 'double', 'min':-2.718}), FloatRange)
    assert isinstance(get_datatype({'type': 'double', 'max':3.14}), FloatRange)
    assert isinstance(get_datatype({'type': 'double', 'min':-9.9, 'max':11.1}),
                      FloatRange)

    with pytest.raises(WrongTypeError):
        get_datatype(['double'])
    with pytest.raises(WrongTypeError):
        get_datatype({'type': 'double', 'min':10, 'max':-10})
    with pytest.raises(WrongTypeError):
        get_datatype(['double', {},  2])

    with pytest.raises(WrongTypeError):
        get_datatype({'type': 'scaled', 'scale':0.01, 'min':-2.718})
    with pytest.raises(WrongTypeError):
        get_datatype({'type': 'scaled', 'scale':0.02, 'max':3.14})
    assert isinstance(get_datatype(
         {'type': 'scaled', 'scale':0.03, 'min':-99, 'max':111}), ScaledInteger)

    dt = ScaledInteger(scale=0.03, min=0, max=9.9)
    assert dt.export_datatype() == {'type': 'scaled', 'max':330, 'min':0, 'scale':0.03}
    assert get_datatype(dt.export_datatype()).export_datatype() == dt.export_datatype()

    with pytest.raises(WrongTypeError):
        get_datatype(['scaled'])    # dict missing
    with pytest.raises(WrongTypeError):
        get_datatype({'type': 'scaled', 'min':-10, 'max':10})  # no scale
    with pytest.raises(WrongTypeError):
        get_datatype({'type': 'scaled', 'min':10, 'max':-10, 'scale': 1})  # limits reversed
    with pytest.raises(WrongTypeError):
        get_datatype(['scaled', {'min':10, 'max':-10, 'scale': 1},  2])

    with pytest.raises(WrongTypeError):
        get_datatype(['enum'])
    with pytest.raises(WrongTypeError):
        get_datatype({'type': 'enum', 'a': -2})
    assert isinstance(get_datatype({'type': 'enum', 'members': {'a': -2}}), EnumType)

    assert isinstance(get_datatype({'type': 'blob', 'maxbytes':1}), BLOBType)
    assert isinstance(get_datatype({'type': 'blob', 'minbytes':1, 'maxbytes':10}), BLOBType)

    with pytest.raises(WrongTypeError):
        get_datatype({'type': 'blob', 'minbytes':10, 'maxbytes':1})
    with pytest.raises(WrongTypeError):
        get_datatype({'type': 'blob', 'minbytes':10, 'maxbytes':-10})
    with pytest.raises(WrongTypeError):
        get_datatype(['blob', {'maxbytes':10}, 'x'])

    assert isinstance(get_datatype({'type': 'string', 'maxchars':1}), StringType)
    assert isinstance(get_datatype({'type': 'string', 'maxchars':1}), StringType)
    assert isinstance(get_datatype({'type': 'string', 'minchars':1, 'maxchars':10}), StringType)

    with pytest.raises(WrongTypeError):
        get_datatype({'type': 'string', 'minchars':10, 'maxchars':1})
    with pytest.raises(WrongTypeError):
        get_datatype({'type': 'string', 'minchars':10, 'maxchars':-10})
    with pytest.raises(WrongTypeError):
        get_datatype(['string', {'maxchars':-0}, 'x'])

    with pytest.raises(WrongTypeError):
        get_datatype(['array'])
    with pytest.raises(WrongTypeError):
        get_datatype({'type': 'array', 'members': [1]})
    assert isinstance(get_datatype({'type': 'array', 'minlen':1, 'maxlen':1,
                                    'members':{'type': 'blob', 'maxbytes':1}}
                                   ), ArrayOf)
    assert isinstance(get_datatype({'type': 'array', 'minlen':1, 'maxlen':1,
                                    'members':{'type': 'blob', 'maxbytes':1}}
                                   ).members, BLOBType)

    with pytest.raises(WrongTypeError):
        get_datatype({'type': 'array', 'members':{'type': 'blob', 'maxbytes':1}, 'minbytes':-10})
    with pytest.raises(WrongTypeError):
        get_datatype({'type': 'array', 'members':{'type': 'blob', 'maxbytes':1},
                                 'min':10, 'max':1})
    with pytest.raises(WrongTypeError):
        get_datatype({'type': 'array', 'blob': {'max': 4}, 'maxbytes': 10})

    with pytest.raises(WrongTypeError):
        get_datatype(['tuple'])
    with pytest.raises(WrongTypeError):
        get_datatype(['tuple', [1], 2, 3])
    assert isinstance(get_datatype(
        {'type': 'tuple', 'members':[{'type': 'blob', 'maxbytes':1}]}), TupleOf)
    assert isinstance(get_datatype(
        {'type': 'tuple', 'members':[{'type': 'blob', 'maxbytes':1}]}).members[0], BLOBType)

    with pytest.raises(WrongTypeError):
        get_datatype({'type': 'tuple', 'members': {}})
    with pytest.raises(WrongTypeError):
        get_datatype(['tuple', 10, -10])

    assert isinstance(get_datatype({'type': 'tuple', 'members':[{'type': 'blob', 'maxbytes':1},
                                                    {'type': 'bool'}]}), TupleOf)

    with pytest.raises(WrongTypeError):
        get_datatype(['struct'])
    with pytest.raises(WrongTypeError):
        get_datatype(['struct', [1], 2, 3])
    assert isinstance(get_datatype({'type': 'struct', 'members':
            {'name': {'type': 'blob', 'maxbytes':1}}}), StructOf)
    assert isinstance(get_datatype({'type': 'struct', 'members':
            {'name': {'type': 'blob', 'maxbytes':1}}}).members['name'], BLOBType)

    with pytest.raises(WrongTypeError):
        get_datatype({'type': 'struct', 'members': {}})
    with pytest.raises(WrongTypeError):
        get_datatype({'type': 'struct', 'members':[1,2,3]})


@pytest.mark.parametrize('dt, contained_in', [
    (FloatRange(-10, 10), FloatRange()),
    (IntRange(-10, 10), FloatRange()),
    (IntRange(-10, 10), IntRange(-20, 10)),
    (FloatRange(-10, 10), FloatRange(-15, 10)),
    (StringType(), StringType(isUTF8=True)),
    (StringType(10, 10), StringType()),
    (ArrayOf(StringType(), 3, 5), ArrayOf(StringType(), 3, 6)),
    (TupleOf(StringType(), BoolType()), TupleOf(StringType(), IntRange())),
    (StructOf(a=FloatRange(-1,1), b=BoolType()), StructOf(a=FloatRange(), b=BoolType(), optional=['b'])),
])
def test_oneway_compatible(dt, contained_in):
    dt.compatible(contained_in)
    with pytest.raises(BadValueError):
        contained_in.compatible(dt)


@pytest.mark.parametrize('dt1, dt2', [
    (FloatRange(-5.5, 5.5), ScaledInteger(10, -5.5, 5.5)),
    (IntRange(0,1), BoolType()),
    (IntRange(-10, 10), IntRange(-10, 10)),
])
def test_twoway_compatible(dt1, dt2):
    dt1.compatible(dt1)
    dt2.compatible(dt2)


@pytest.mark.parametrize('dt1, dt2', [
    (StringType(), FloatRange()),
    (IntRange(-10, 10), StringType()),
    (StructOf(a=BoolType(), b=BoolType()), ArrayOf(StringType(), 2)),
    (ArrayOf(BoolType(), 2), TupleOf(BoolType(), StringType())),
    (TupleOf(BoolType(), BoolType()), StructOf(a=BoolType(), b=BoolType())),
    (ArrayOf(StringType(), 3), ArrayOf(BoolType(), 3)),
    (TupleOf(StringType(), BoolType()), TupleOf(BoolType(), BoolType())),
    (StructOf(a=FloatRange(-1, 1), b=StringType()), StructOf(a=FloatRange(), b=BoolType())),
])
def test_incompatible(dt1, dt2):
    with pytest.raises(BadValueError):
        dt1.compatible(dt2)
    with pytest.raises(BadValueError):
        dt2.compatible(dt1)


@pytest.mark.parametrize('dt', [FloatRange(), IntRange(), ScaledInteger(1)])
def test_lazy_validation(dt):
    generalConfig.defaults['lazy_number_validation'] = True
    dt('0')
    generalConfig.defaults['lazy_number_validation'] = False
    with pytest.raises(WrongTypeError):
        dt('0')


mytuple = TupleOf(ScaledInteger(0.1, 0, 10, unit='$'), FloatRange(unit='$/min'))
myarray = ArrayOf(mytuple)


@pytest.mark.parametrize('unit, dt', [
    ('m', FloatRange(unit='$/sec')),
    ('A', mytuple),
    ('V', myarray),
    ('X', StructOf(a=myarray, b=mytuple)),
])
def test_main_unit(unit, dt):
    fixed_dt = dt.copy()
    fixed_dt.set_main_unit(unit)
    before = repr(dt.export_datatype())
    after = repr(fixed_dt.export_datatype())
    assert '$' in before
    assert before != after
    assert before.replace('$', unit) == after

def ex_validator(i):
    if i > 10:
        raise RuntimeError('too large')
    return i

@pytest.mark.parametrize('validator, value, result', [
    (dict, [('a', 1)], {'a': 1}),
    (ex_validator, 5, 5),
    # pylint: disable=unnecessary-lambda
    (lambda x: dict(x), {'a': 1}, {'a': 1}),
    # pylint: disable=unnecessary-lambda
    (lambda i: ex_validator(i) * 3, 3, 9),
])
def test_value_type(validator, value, result):
    t = ValueType()
    tv = ValueType(validator)
    assert t(value) == value
    assert tv(value) == result


@pytest.mark.parametrize('validator, value', [
    (dict, 'strinput'),
    (ex_validator, 20),
    # pylint: disable=unnecessary-lambda
    (lambda i: list(i), 1),
])
def test_value_type_rejecting(validator, value):
    t = ValueType()
    tv = ValueType(validator)
    assert t(value) == value
    with pytest.raises(ConfigError):
        tv(value)
