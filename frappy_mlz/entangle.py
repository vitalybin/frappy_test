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
#   Alexander Lenz <alexander.lenz@frm2.tum.de>
#   Enrico Faulhaber <enrico.faulhaber@frm2.tum.de>
#
# *****************************************************************************

# This is based upon the entangle-nicos integration
"""This module contains the MLZ SECoP - TANGO integration.

Here we support devices which fulfill the official
MLZ TANGO interface for the respective device classes.
"""

# pylint: disable=too-many-lines, consider-using-f-string

import re
import sys
import threading
from time import sleep, time as currenttime

import PyTango

from frappy.datatypes import ArrayOf, EnumType, FloatRange, IntRange, \
    LimitsType, StatusType, StringType, TupleOf, ValueType
from frappy.errors import CommunicationFailedError, ConfigError, \
    HardwareError, ProgrammingError, WrongTypeError, RangeError
from frappy.lib import lazy_property
from frappy.modules import Command, Drivable, Module, Parameter, Property, \
    Readable, Writable

#####


# Only export these classes for 'from frappy_mlz import *'
__all__ = [
    'AnalogInput', 'Sensor',
    'AnalogOutput', 'Actuator', 'Motor',
    'TemperatureController', 'PowerSupply',
    'DigitalInput', 'NamedDigitalInput', 'PartialDigitalInput',
    'DigitalOutput', 'NamedDigitalOutput', 'PartialDigitalOutput',
    'StringIO',
]

EXC_MAPPING = {
    PyTango.CommunicationFailed: CommunicationFailedError,
    PyTango.WrongNameSyntax: ConfigError,
    PyTango.DevFailed: HardwareError,
}

REASON_MAPPING = {
    'Entangle_ConfigurationError': ConfigError,
    'Entangle_WrongAPICall': ProgrammingError,
    'Entangle_CommunicationFailure': CommunicationFailedError,
    'Entangle_InvalidValue': ValueError,
    'Entangle_ProgrammingError': ProgrammingError,
    'Entangle_HardwareFailure': HardwareError,
}

# Tango DevFailed reasons that should not cause a retry
FATAL_REASONS = {
    'Entangle_ConfigurationError',
    'Entangle_UnrecognizedHardware',
    'Entangle_WrongAPICall',
    'Entangle_InvalidValue',
    'Entangle_NotSupported',
    'Entangle_ProgrammingError',
    'DB_DeviceNotDefined',
    'API_DeviceNotDefined',
    'API_CantConnectToDatabase',
    'API_TangoHostNotSet',
    'API_ServerNotRunning',
    'API_DeviceNotExported',
}


def describe_dev_error(exc):
    """Return a better description for a Tango exception.

    Most Tango exceptions are quite verbose and not suitable for user
    consumption.  Map the most common ones, that can also happen during normal
    operation, to a bit more friendly ones.
    """
    # general attributes
    reason = exc.reason.strip()
    fulldesc = reason + ': ' + exc.desc.strip()
    # reduce Python tracebacks
    if '\n' in exc.origin and 'File ' in exc.origin:
        origin = exc.origin.splitlines()[-2].strip()
    else:
        origin = exc.origin.strip()

    # we don't need origin info for Tango itself
    if origin.startswith(('DeviceProxy::', 'DeviceImpl::', 'Device_3Impl::',
                          'Device_4Impl::', 'Connection::', 'TangoMonitor::')):
        origin = None

    # now handle specific cases better
    if reason == 'API_AttrNotAllowed':
        m = re.search(r'to (read|write) attribute (\w+)', fulldesc)
        if m:
            if m.group(1) == 'read':
                fulldesc = 'reading %r not allowed in current state'
            else:
                fulldesc = 'writing %r not allowed in current state'
            fulldesc %= m.group(2)
    elif reason == 'API_CommandNotAllowed':
        m = re.search(r'Command (\w+) not allowed when the '
                      r'device is in (\w+) state', fulldesc)
        if m:
            fulldesc = f'executing {m.group(1)!r} not allowed in state {m.group(2)}'
    elif reason == 'API_DeviceNotExported':
        m = re.search(r'Device ([\w/]+) is not', fulldesc)
        if m:
            fulldesc = f'Tango device {m.group(1)} is not exported, is the server running?'
    elif reason == 'API_CorbaException':
        if 'TRANSIENT_CallTimedout' in fulldesc:
            fulldesc = 'Tango client-server call timed out'
        elif 'TRANSIENT_ConnectFailed' in fulldesc:
            fulldesc = 'connection to Tango server failed, is the server ' \
                'running?'
    elif reason == 'API_CantConnectToDevice':
        m = re.search(r'connect to device ([\w/]+)', fulldesc)
        if m:
            fulldesc = f'connection to Tango device {m.group(1)} failed, is the server running?'
    elif reason == 'API_CommandTimedOut':
        if 'acquire serialization' in fulldesc:
            fulldesc = 'Tango call timed out waiting for lock on server'

    # append origin if wanted
    if origin:
        fulldesc += f' in {origin}'
    return fulldesc


class BasePyTangoDevice:
    """
    Basic PyTango device.

    The PyTangoDevice uses an internal PyTango.DeviceProxy but wraps command
    execution and attribute operations with logging and exception mapping.
    """

    # parameters
    comtries = Parameter('Maximum retries for communication',
                         datatype=IntRange(1, 100), default=3, readonly=False,
                         group='communication')
    comdelay = Parameter('Delay between retries', datatype=FloatRange(0),
                         unit='s', default=0.1, readonly=False,
                         group='communication')
    tangodevice = Parameter('Tango device name',
                            datatype=StringType(), readonly=True,
                            # export=True,   # for testing only
                            export=False,
                            )

    tango_status_mapping = {
        PyTango.DevState.ON:     StatusType.IDLE,
        PyTango.DevState.ALARM:  StatusType.WARN,
        PyTango.DevState.OFF:    StatusType.DISABLED,
        PyTango.DevState.FAULT:  StatusType.ERROR,
        PyTango.DevState.MOVING: StatusType.BUSY,
    }

    @lazy_property
    def _com_lock(self):
        return threading.Lock()

    def _com_retry(self, info, function, *args, **kwds):
        """Try communicating with the hardware/device.

        Parameter "info" is passed to _com_return and _com_raise methods that
        process the return value or exception raised after maximum tries.
        """
        tries = self.comtries
        with self._com_lock:
            while True:
                tries -= 1
                try:
                    result = function(*args, **kwds)
                    return self._com_return(result, info)
                except Exception as err:
                    if tries == 0:
                        self._com_raise(err, info)
                    else:
                        name = getattr(function, '__name__', 'communication')
                        self._com_warn(tries, name, err, info)
                    sleep(self.comdelay)

    def earlyInit(self):
        # Wrap PyTango client creation (so even for the ctor, logging and
        # exception mapping is enabled).
        self._createPyTangoDevice = self._applyGuardToFunc(
            self._createPyTangoDevice, 'constructor')
        super().earlyInit()

    @lazy_property
    def _dev(self):
        # for startup be very permissive, wait up to 15 min per device
        settings = self.comdelay, self.comtries
        self.comdelay, self.comtries = 10, 90
        res = self._createPyTangoDevice(self.tangodevice)
        self.comdelay, self.comtries = settings
        return res

    def _hw_wait(self):
        """Wait until hardware status is not BUSY."""
        while self.read_status()[0] == Drivable.Status.BUSY:
            sleep(0.3)

    def _getProperty(self, name, dev=None):
        """
        Utility function for getting a property by name easily.
        """
        if dev is None:
            dev = self._dev
        # Entangle and later API
        if dev.command_query('GetProperties').in_type == PyTango.DevVoid:
            props = dev.GetProperties()
            return props[props.index(name) + 1] if name in props else None
        # old (pre-Entangle) API
        return dev.GetProperties([name, 'device'])[2]

    def _createPyTangoDevice(self, address):  # pylint: disable=E0202
        """
        Creates the PyTango DeviceProxy and wraps command execution and
        attribute operations with logging and exception mapping.
        """
        device = PyTango.DeviceProxy(address)
        # detect not running and not exported devices early, because that
        # otherwise would lead to attribute errors later
        try:
            device.State
        except AttributeError as e:
            raise CommunicationFailedError(
                self, 'connection to Tango server failed, '
                'is the server running?') from e
        return self._applyGuardsToPyTangoDevice(device)

    def _applyGuardsToPyTangoDevice(self, dev):
        """
        Wraps command execution and attribute operations of the given
        device with logging and exception mapping.
        """
        dev.__dict__['command_inout'] = self._applyGuardToFunc(dev.command_inout)
        dev.__dict__['write_attribute'] = self._applyGuardToFunc(dev.write_attribute,
                                                     'attr_write')
        dev.__dict__['read_attribute'] = self._applyGuardToFunc(dev.read_attribute,
                                                    'attr_read')
        dev.__dict__['attribute_query'] = self._applyGuardToFunc(dev.attribute_query,
                                                     'attr_query')
        return dev

    def _applyGuardToFunc(self, func, category='cmd'):
        """
        Wrap given function with logging and exception mapping.
        """
        def wrap(*args, **kwds):
            # handle different types for better debug output
            if category == 'cmd':
                self.log.debug('[PyTango] command: %s%r', args[0], args[1:])
            elif category == 'attr_read':
                self.log.debug('[PyTango] read attribute: %s', args[0])
            elif category == 'attr_write':
                self.log.debug('[PyTango] write attribute: %s => %r',
                               args[0], args[1:])
            elif category == 'attr_query':
                self.log.debug('[PyTango] query attribute properties: %s',
                               args[0])
            elif category == 'constructor':
                self.log.debug('[PyTango] device creation: %s', args[0])
            elif category == 'internal':
                self.log.debug('[PyTango integration] internal: %s%r',
                               func.__name__, args)
            else:
                self.log.debug('[PyTango] call: %s%r', func.__name__, args)

            info = category + ' ' + args[0] if args else category
            return self._com_retry(info, func, *args, **kwds)

        # hide the wrapping
        wrap.__name__ = func.__name__

        return wrap

    def _com_return(self, result, info):
        """Process *result*, the return value of communication.

        Can raise an exception to initiate a retry.  Default is to return
        result unchanged.
        """
        # XXX: explicit check for loglevel to avoid expensive reprs
        if isinstance(result, PyTango.DeviceAttribute):
            the_repr = repr(result.value)[:300]
        else:
            # This line explicitly logs '=> None' for commands which
            # does not return a value. This indicates that the command
            # execution ended.
            the_repr = repr(result)[:300]
        self.log.debug('\t=> %s', the_repr)
        return result

    def _tango_exc_desc(self, err):
        exc = str(err)
        if err.args:
            exc = err.args[0]  # Can be str or DevError
            if isinstance(exc, PyTango.DevError):
                return describe_dev_error(exc)
        return exc

    def _tango_exc_reason(self, err):
        if err.args and isinstance(err.args[0], PyTango.DevError):
            return err.args[0].reason.strip()
        return ''

    def _com_warn(self, retries, name, err, info):
        """Gives the opportunity to warn the user on failed tries.

        Can also call _com_raise to abort early.
        """
        if self._tango_exc_reason(err) in FATAL_REASONS:
            self._com_raise(err, info)
        if retries == self.comtries - 1:
            self.log.warning('%s failed, retrying up to %d times: %s',
                             info, retries, self._tango_exc_desc(err))

    def _com_raise(self, err, info):
        """Process the exception raised either by communication or _com_return.

        Should raise a NICOS exception.  Default is to raise
        CommunicationFailedError.
        """
        reason = self._tango_exc_reason(err)
        exclass = REASON_MAPPING.get(
            reason, EXC_MAPPING.get(type(err), CommunicationFailedError))
        fulldesc = self._tango_exc_desc(err)
        self.log.debug('PyTango error: %s', fulldesc)
        raise exclass(self, fulldesc)

    @Command(argument=None, result=None)
    def reset(self):
        """Tango reset command"""
        self._dev.Reset()


class PyTangoDevice(BasePyTangoDevice):
    """Base for "normal" devices with status."""

    status = Parameter(datatype=StatusType(Readable, 'UNKNOWN', 'DISABLED'))

    def read_status(self):
        # Query status code and string
        tangoState = self._dev.State()
        tangoStatus = self._dev.Status()

        # Map status
        myState = self.tango_status_mapping.get(tangoState, StatusType.UNKNOWN)

        return (myState, tangoStatus)


class AnalogInput(PyTangoDevice, Readable):
    """
    The AnalogInput handles all devices only delivering an analogue value.
    """
    __main_unit = None

    def applyMainUnit(self, mainunit):
        # called from __init__ method
        # replacement of '$' by main unit must be done later
        self.__main_unit = mainunit

    def startModule(self, start_events):
        super().startModule(start_events)
        try:
            # query unit from tango and update value property
            attrInfo = self._dev.attribute_query('value')
            # prefer configured unit if nothing is set on the Tango device, else
            # update
            if attrInfo.unit != 'No unit':
                self.accessibles['value'].datatype.setProperty('unit', attrInfo.unit)
                self.__main_unit = attrInfo.unit
        except Exception as e:
            self.log.error(e)
        if self.__main_unit:
            super().applyMainUnit(self.__main_unit)

    def read_value(self):
        return self._dev.value


class Sensor(AnalogInput):
    """
    The sensor interface describes all analog read only devices.

    The difference to AnalogInput is that the “value” attribute can be
    converted from the “raw value” to a physical value with an offset and a
    formula.
    """
    # note: we don't transport the formula to secop....
    #       we support the adjust method

    @Command(argument=FloatRange(), result=None)
    def setposition(self, value):
        """Set the position to the given value."""
        self._dev.Adjust(value)


class AnalogOutput(PyTangoDevice, Drivable):
    """The AnalogOutput handles all devices which set an analogue value.

    The main application field is the output of any signal which may be
    considered as continously in a range. The values may have nearly any
    value between the limits. The compactness is limited by the resolution of
    the hardware.

    This class should be considered as a base class for motors, temperature
    controllers, ...
    """

    # parameters
    userlimits = Parameter('User defined limits of device value',
                           datatype=LimitsType(FloatRange(unit='$')),
                           default=(float('-Inf'), float('+Inf')),
                           readonly=False,
                           )
    abslimits = Parameter('Absolute limits of device value',
                          datatype=LimitsType(FloatRange(unit='$')),
                          export=False,
                          )
    precision = Parameter('Precision of the device value (allowed deviation '
                          'of stable values from target)',
                          datatype=FloatRange(1e-38, unit='$'),
                          readonly=False, group='stability',
                          )
    window = Parameter('Time window for checking stabilization if > 0',
                       default=60.0, readonly=False,
                       datatype=FloatRange(0, 900, unit='s'), group='stability',
                       )
    timeout = Parameter('Timeout for waiting for a stable value (if > 0)',
                        default=60.0, readonly=False,
                        datatype=FloatRange(0, 900, unit='s'), group='stability',
                        )
    status = Parameter(datatype=StatusType(PyTangoDevice, 'BUSY', 'UNSTABLE'))

    _history = ()
    _timeout = None
    _moving = False
    __main_unit = None

    def applyMainUnit(self, mainunit):
        # called from __init__ method
        # replacement of '$' by main unit must be done later
        self.__main_unit = mainunit

    def _init_limits(self):
        """Get abslimits from tango if not configured. Otherwise, check if both
        ranges are compatible."""

        def intersect_limits(first, second, first_kind, second_kind):
            lower = max(first[0], second[0])
            upper = min(first[1], second[1])
            if lower >= upper:
                raise WrongTypeError(f"{first_kind} limits '{first}' are not "
                                     f"compatible with {second_kind} limits "
                                     f"'{second}'!")
            return lower, upper

        tangoabslim = (-sys.float_info.max, sys.float_info.max)
        try:
            read_tangoabslim = (float(self._getProperty('absmin')),
                                float(self._getProperty('absmax')))
            # Entangle convention for "unrestricted"
            if read_tangoabslim != (0, 0):
                tangoabslim = read_tangoabslim
        except Exception as e:
            self.log.error('could not read Tango abslimits: %s' % e)

        if self.parameters['abslimits'].readerror:
            # no abslimits configured in frappy
            self.parameters['abslimits'].readerror = None
            self.abslimits = tangoabslim

        # check both abslimits against each other
        self.abslimits = intersect_limits(self.abslimits, tangoabslim,
                                          'frappy absolute',
                                          'entangle absolute')

        # set abslimits as hard target limits
        self.parameters['target'].datatype.set_properties(
            min=self.abslimits[0], max=self.abslimits[1])

        # restrict current user limits by abslimits
        self.userlimits = intersect_limits(self.userlimits, self.abslimits,
                                           'user', 'absolute')

        # restrict settable user limits by abslimits
        self.parameters['userlimits'].datatype.members[0].set_properties(
            min=self.abslimits[0], max=self.abslimits[1])
        self.parameters['userlimits'].datatype.members[1].set_properties(
            min=self.abslimits[0], max=self.abslimits[1])

    def initModule(self):
        super().initModule()
        # init history
        self._history = []  # will keep (timestamp, value) tuple
        self._timeout = None  # keeps the time at which we will timeout, or None

    def startModule(self, start_events):
        super().startModule(start_events)
        try:
            # query unit from tango and update value property
            attrInfo = self._dev.attribute_query('value')
            # prefer configured unit if nothing is set on the Tango device, else
            # update
            if attrInfo.unit != 'No unit':
                self.accessibles['value'].datatype.setProperty('unit', attrInfo.unit)
                self.__main_unit = attrInfo.unit
        except Exception as e:
            self.log.error(e)
        super().applyMainUnit(self.__main_unit)
        self._init_limits()

    def doPoll(self):
        super().doPoll()
        while len(self._history) > 2:
            # if history would be too short, break
            if self._history[-1][0] - self._history[1][0] <= self.window:
                break
            # else: remove a stale point
            self._history.pop(0)

    def read_value(self):
        value = self._dev.value
        self._history.append((currenttime(), value))
        return value

    def read_target(self):
        attrObj = self._dev.read_attribute('value')
        return attrObj.w_value

    def _isAtTarget(self):
        if self.target is None:
            return True  # avoid bootstrapping problems
        if not self._history:
            return False  # no history -> no knowledge
        # check subset of _history which is in window
        # also check if there is at least one value before window
        # to know we have enough datapoints
        hist = self._history[:]
        window_start = currenttime() - self.window
        hist_in_window = [v for (t, v) in hist if t >= window_start]
        if len(hist) == len(hist_in_window):
            return False  # no data point before window
        if not hist_in_window:
            # window is too small -> use last point only
            hist_in_window = [self.value]

        max_in_hist = max(hist_in_window)
        min_in_hist = min(hist_in_window)
        stable = max_in_hist - min_in_hist <= self.precision
        at_target = max_in_hist - self.precision <= self.target <= min_in_hist + self.precision

        return stable and at_target

    def read_status(self):
        status = super().read_status()
        if status[0] in (StatusType.DISABLED, StatusType.ERROR):
            self.setFastPoll(False)
            return status
        if self._isAtTarget():
            self._timeout = None
            self._moving = False
        else:
            if self._timeout and self._timeout < currenttime():
                status = self.Status.UNSTABLE, 'timeout after waiting for stable value'
            elif self._moving:
                status = (self.Status.BUSY, 'moving: ' + status[1])
        self.setFastPoll(self.isBusy(status))
        return status

    @property
    def absmin(self):
        return self.abslimits[0]

    @property
    def absmax(self):
        return self.abslimits[1]

    def __getusermin(self):
        return max(self.userlimits[0], self.abslimits[0])

    def __setusermin(self, value):
        self.userlimits = (value, self.userlimits[1])

    usermin = property(__getusermin, __setusermin)

    def __getusermax(self):
        return min(self.userlimits[1], self.abslimits[1])

    def __setusermax(self, value):
        self.userlimits = (self.userlimits[0], value)

    usermax = property(__getusermax, __setusermax)

    del __getusermin, __setusermin, __getusermax, __setusermax

    def write_userlimits(self, value):
        umin, umax = value
        amin, amax = self.abslimits
        if umin < amin - abs(amin * 1e-12):
            umin = amin
        if umax > amax + abs(amax * 1e-12):
            umax = amax
        return umin, umax

    def write_target(self, value=FloatRange()):
        umin, umax = self.userlimits
        if not umin <= value <= umax:
            raise RangeError(
                f'target value {value} must be between {umin} and {umax}')
        if self.status[0] == self.Status.BUSY:
            # changing target value during movement is not allowed by the
            # Tango base class state machine. If we are moving, stop first.
            self.stop()
            self._hw_wait()
        self._dev.value = value
        # set meaningful timeout
        self._timeout = currenttime() + self.window + self.timeout
        if hasattr(self, 'ramp'):
            self._timeout += abs((self.target or self.value) - self.value) / \
                    ((self.ramp or 1e-8) * 60)
        elif hasattr(self, 'speed'):
            self._timeout += abs((self.target or self.value) - self.value) / \
                    (self.speed or 1e-8)
        if not self.timeout:
            self._timeout = None
        self._moving = True
        # do not clear the history here:
        #    - if the target is not changed by more than precision, there is no need to wait
        # self._history = []
        self.read_status()  # poll our status to keep it updated (this will also set fast poll)
        return self.read_target()

    def _hw_wait(self):
        while super().read_status()[0] == self.Status.BUSY:
            sleep(0.3)

    def stop(self):
        """cease driving, go to IDLE state"""
        self._dev.Stop()


class Actuator(AnalogOutput):
    """The aAtuator interface describes all analog devices which DO something
    in a defined way.

    The difference to AnalogOutput is that there is a speed attribute, and the
    value attribute is converted from the “raw value” with a formula and
    offset.
    """
    # for secop: support the speed and ramp parameters

    # parameters
    speed = Parameter('The speed of changing the value',
                      readonly=False, datatype=FloatRange(0, unit='$/s'),
                      )
    ramp = Parameter('The speed of changing the value',
                     readonly=False, datatype=FloatRange(0, unit='$/min'),
                     )

    def read_speed(self):
        return self._dev.speed

    def write_speed(self, value):
        self._dev.speed = value

    def read_ramp(self):
        return self.read_speed() * 60

    def write_ramp(self, value):
        self.write_speed(value / 60.)
        return self.read_speed() * 60

    @Command(FloatRange(), result=None)
    def setposition(self, value=FloatRange()):
        """Set the position to the given value."""
        self._dev.Adjust(value)


class Motor(Actuator):
    """This class implements a motor device (in a sense of a real motor
    (stepper motor, servo motor, ...)).

    It has the ability to move a real object from one place to another place.
    """

    # parameters
    refpos = Parameter('Reference position',
                       datatype=FloatRange(unit='$'),
                       )
    accel = Parameter('Acceleration',
                      datatype=FloatRange(unit='$/s^2'), readonly=False,
                      )
    decel = Parameter('Deceleration',
                      datatype=FloatRange(unit='$/s^2'), readonly=False,
                      )

    def read_refpos(self):
        return float(self._getProperty('refpos'))

    def read_accel(self):
        return self._dev.accel

    def write_accel(self, value):
        self._dev.accel = value

    def read_decel(self):
        return self._dev.decel

    def write_decel(self, value):
        self._dev.decel = value

    @Command()
    def reference(self):
        """Do a reference run"""
        self._dev.Reference()
        return self.read_value()


class TemperatureController(Actuator):
    """A temperature control loop device.
    """

    # parameters
    # pylint: disable=invalid-name
    p = Parameter('Proportional control Parameter', datatype=FloatRange(),
                  readonly=False, group='pid',
                  )
    i = Parameter('Integral control Parameter', datatype=FloatRange(),
                  readonly=False, group='pid',
                  )
    d = Parameter('Derivative control Parameter', datatype=FloatRange(),
                  readonly=False, group='pid',
                  )
    pid = Parameter('pid control Parameters',
                    datatype=TupleOf(FloatRange(), FloatRange(), FloatRange()),
                    readonly=False, group='pid',
                    )
    setpoint = Parameter('Current setpoint', datatype=FloatRange(unit='$'),
                         )
    heateroutput = Parameter('Heater output', datatype=FloatRange(),
                             )

    # overrides
    precision = Parameter(default=0.1)
    ramp = Parameter(description='Temperature ramp')

    def doPoll(self):
        super().doPoll()
        self.read_setpoint()
        self.read_heateroutput()

    def read_ramp(self):
        return self._dev.ramp

    def write_ramp(self, value):
        self._dev.ramp = value
        return self._dev.ramp

    def read_p(self):
        return self._dev.p

    def write_p(self, value):
        self._dev.p = value

    def read_i(self):
        return self._dev.i

    def write_i(self, value):
        self._dev.i = value

    def read_d(self):
        return self._dev.d

    def write_d(self, value):
        self._dev.d = value

    def read_pid(self):
        self.read_p()
        self.read_i()
        self.read_d()
        return self.p, self.i, self.d

    def write_pid(self, value):
        self._dev.p = value[0]
        self._dev.i = value[1]
        self._dev.d = value[2]

    def read_setpoint(self):
        return self._dev.setpoint

    def read_heateroutput(self):
        return self._dev.heaterOutput

    # remove UserCommand setposition from Actuator
    # (makes no sense for a TemperatureController)
    setposition = None


class PowerSupply(Actuator):
    """A power supply (voltage and current) device.
    """

    # parameters
    voltage = Parameter('Actual voltage',
                        datatype=FloatRange(unit='V'))
    current = Parameter('Actual current',
                        datatype=FloatRange(unit='A'))

    # overrides
    ramp = Parameter(description='Current/voltage ramp')

    def doPoll(self):
        super().doPoll()
        # TODO: poll voltage and current faster when busy
        self.read_voltage()
        self.read_current()

    def read_ramp(self):
        return self._dev.ramp

    def write_ramp(self, value):
        self._dev.ramp = value

    def read_voltage(self):
        return self._dev.voltage

    def read_current(self):
        return self._dev.current


class DigitalInput(PyTangoDevice, Readable):
    """A device reading a bitfield.
    """

    # overrides
    value = Parameter(datatype=IntRange())

    def read_value(self):
        return self._dev.value


class NamedDigitalInput(DigitalInput):
    """A DigitalInput with numeric values mapped to names.
    """

    # parameters
    mapping = Property('A dictionary mapping state names to integers',
                       datatype=ValueType(dict))

    def initModule(self):
        super().initModule()
        try:
            mapping = self.mapping
            self.accessibles['value'].setProperty('datatype', EnumType('value', **mapping))
        except Exception as e:
            raise ValueError(f'Illegal Value for mapping: {self.mapping!r}') from e

    def read_value(self):
        value = self._dev.value
        return value  # mapping is done by datatype upon export()


class PartialDigitalInput(NamedDigitalInput):
    """Base class for a TANGO DigitalInput with only a part of the full
    bit width accessed.
    """

    # parameters
    startbit = Parameter('Number of the first bit',
                         datatype=IntRange(0), default=0)
    bitwidth = Parameter('Number of bits',
                         datatype=IntRange(0), default=1)

    def initModule(self):
        super().initModule()
        self._mask = (1 << self.bitwidth) - 1
        # self.accessibles['value'].datatype = IntRange(0, self._mask)

    def read_value(self):
        raw_value = self._dev.value
        value = (raw_value >> self.startbit) & self._mask
        return value  # mapping is done by datatype upon export()


class DigitalOutput(PyTangoDevice, Drivable):
    """A device that can set and read a digital value corresponding to a
    bitfield.
    """

    # overrides
    value = Parameter('current value', datatype=IntRange())
    target = Parameter('target value', datatype=IntRange())
    status = Parameter(datatype=StatusType(Drivable, 'BUSY'))  # for some reason, just deriving from Drivable doesn't work

    def read_value(self):
        return self._dev.value  # mapping is done by datatype upon export()

    def read_status(self):
        status = super().read_status()
        self.setFastPoll(self.isBusy(status))
        return status

    def write_target(self, value):
        self._dev.value = value
        self.read_value()
        self.read_status()  # this will also set fast poll
        return self.read_target()

    def read_target(self):
        attrObj = self._dev.read_attribute('value')
        return attrObj.w_value


class NamedDigitalOutput(DigitalOutput):
    """A DigitalOutput with numeric values mapped to names.
    """

    # parameters
    mapping = Property('A dictionary mapping state names to integers',
                       datatype=ValueType(dict))

    def initModule(self):
        super().initModule()
        try:
            mapping = self.mapping
            self.accessibles['value'].setProperty('datatype', EnumType('value', **mapping))
            self.accessibles['target'].setProperty('datatype', EnumType('target', **mapping))
        except Exception as e:
            raise ValueError(f'Illegal Value for mapping: {self.mapping!r}') from e

    def write_target(self, value):
        # map from enum-str to integer value
        self._dev.value = int(value)
        self.read_value()
        return self.read_target()


class PartialDigitalOutput(NamedDigitalOutput):
    """Base class for a TANGO DigitalOutput with only a part of the full
    bit width accessed.
    """

    # parameters
    startbit = Parameter('Number of the first bit',
                         datatype=IntRange(0), default=0)
    bitwidth = Parameter('Number of bits',
                         datatype=IntRange(0), default=1)

    def initModule(self):
        super().initModule()
        self._mask = (1 << self.bitwidth) - 1
        # self.accessibles['value'].datatype = IntRange(0, self._mask)
        # self.accessibles['target'].datatype = IntRange(0, self._mask)

    def read_value(self):
        raw_value = self._dev.value
        value = (raw_value >> self.startbit) & self._mask
        return value  # mapping is done by datatype upon export()

    def write_target(self, value):
        curvalue = self._dev.value
        newvalue = (curvalue & ~(self._mask << self.startbit)) | \
                   (value << self.startbit)
        self._dev.value = newvalue
        self.read_value()
        return self.read_target()


class StringIO(BasePyTangoDevice, Module):
    """StringIO abstracts communication over a hardware bus that sends and
    receives strings.
    """

    # parameters
    bustimeout = Parameter('Communication timeout',
                           datatype=FloatRange(unit='s'), readonly=False,
                           group='communication')
    endofline = Parameter('End of line',
                          datatype=StringType(), readonly=False,
                          group='communication')
    startofline = Parameter('Start of line',
                            datatype=StringType(), readonly=False,
                            group='communication')

    def read_bustimeout(self):
        return self._dev.communicationTimeout

    def write_bustimeout(self, value):
        self._dev.communicationTimeout = value

    def read_endofline(self):
        return self._dev.endOfLine

    def write_endofline(self, value):
        self._dev.endOfLine = value

    def read_startofline(self):
        return self._dev.startOfLine

    def write_startofline(self, value):
        self._dev.startOfLine = value

    @Command(argument=StringType(), result=StringType())
    def communicate(self, value=StringType()):
        """Send a string and return the reply"""
        return self._dev.Communicate(value)

    @Command(argument=None, result=None)
    def flush(self):
        """Flush output buffer"""
        self._dev.Flush()

    @Command(argument=IntRange(0), result=StringType())
    def read(self, value):
        """read some characters from input buffer"""
        return self._dev.Read(value)

    @Command(argument=StringType(), result=None)
    def write(self, value):
        """write some chars to output"""
        return self._dev.Write(value)

    @Command(argument=None, result=StringType())
    def readLine(self):
        """Read sol - a whole line - eol"""
        return self._dev.ReadLine()

    @Command(argument=StringType(), result=None)
    def writeLine(self, value):
        """write sol + a whole line + eol"""
        return self._dev.WriteLine(value)

    @Command(argument=ArrayOf(TupleOf(StringType(), IntRange()), 100),
             result=ArrayOf(StringType(), 100))
    def multiCommunicate(self, value):
        """perform a sequence of communications"""
        return self._dev.MultiCommunicate(value)

    @Command(argument=None, result=IntRange(0))
    def availableChars(self):
        """return number of chars in input buffer"""
        return self._dev.availableChars

    @Command(argument=None, result=IntRange(0))
    def availableLines(self):
        """return number of lines in input buffer"""
        return self._dev.availableLines
