HeLevel - a Simple Driver
=========================

Coding the Driver
-----------------
For this tutorial we choose as an example a cryostat. Let us start with the helium level
meter, as this is the simplest module.
As mentioned in the introduction, we have to code the access to the hardware (driver),
and the Frappy framework will deal with the SECoP interface. The code for the driver is
located in a subdirectory named after the facility or institute programming the driver
in our case *frappy_psi*. We create a file named from the electronic device CCU4 we use
here for the He level reading.

CCU4 luckily has a very simple and logical protocol:

* ``<name>=<value>\n`` sets the parameter named ``<name>`` to the value ``<value>``
* ``<name>\n`` reads the parameter named ``<name>``
* in both cases, the reply is ``<name>=<value>\n``

``frappy_psi/ccu4.py``:

.. code:: python

    # the most common Frappy classes can be imported from frappy.core
    from frappy.core import Readable, Parameter, FloatRange, BoolType, StringIO, HasIO


    class CCU4IO(StringIO):
        """communication with CCU4"""
        # for completeness: (not needed, as it is the default)
        end_of_line = '\n'
        # on connect, we send 'cid' and expect a reply starting with 'CCU4'
        # 'cid' is a CCU4 command returning the current version prefixed with CCU4
        identification = [('cid', r'CCU4.*')]


    # inheriting HasIO allows us to use the communicate method for talking with the hardware
    # 'Readable' as base class defines the value and status parameters
    class HeLevel(HasIO, Readable):
        """He Level channel of CCU4"""

        # define the communication class for automatic creation of the IO module
        ioClass = CCU4IO

        # define or alter the parameters
        # as Readable.value exists already, we give only the modified property 'unit'
        value = Parameter(unit='%')

        def read_value(self):
            # method for reading the main value
            reply = self.communicate('h')  # send 'h\n' and get the reply 'h=<value>\n'
            name, txtvalue = reply.split('=')
            assert name == 'h'  # check that we got a reply to our command
            return float(txtvalue)


The class :class:`frappy_psi.ccu4.CCU4IO`, an extension of (:class:`frappy.stringio.StringIO`)
serves as communication class.

:Note:

    You might wonder why the parameter *value* is declared here as class attribute.
    In Python, usually class attributes are used to set a default value which might
    be overwritten in a method. But class attributes can do more, look for Python
    descriptors or properties if you are interested in details.
    In Frappy, the *Parameter* class is a descriptor, which does the magic needed for
    the SECoP interface. Given ``lev`` as an instance of the class ``HeLevel`` above,
    ``lev.value`` will just return its internal cached value.
    ``lev.value = 85.3`` will try to convert to the data type of the parameter,
    put it to the internal cache and send a messages to the SECoP clients telling
    that ``lev.value`` has got a new value.
    For getting a value from the hardware, you have to call ``lev.read_value()``.
    Frappy has replaced your version of *read_value* with a wrapped one which
    also takes care to announce the change to the clients.
    Even when you did not code this method, Frappy adds it silently, so calling
    ``<module>.read_<parameter>`` will be possible for all parameters declared
    in a module.

Above is already the code for a very simple working He Level meter driver. For a next step,
we want to improve it:

* We should inform the client about errors. That is what the *status* parameter is for.
* We want to be able to configure the He Level sensor.
* We want to be able to switch the Level Monitor to fast reading before we start to fill.

Let us start to code these additions. We do not need to declare the status parameter,
as it is inherited from *Readable*. But we declare the new parameters *empty_length*,
*full_length* and *sample_rate*, and we have to code the communication and convert
the status codes from the hardware to the standard SECoP status codes.

.. code:: python

        ...
        # the first two arguments to Parameter are 'description' and 'datatype'
        # it is highly recommended to define always the physical unit
        empty_length = Parameter('warm length when empty', FloatRange(0, 2000, unit='mm'),
                                 readonly=False)
        full_length = Parameter('warm length when full', FloatRange(0, 2000, unit='mm'),
                                readonly=False)
        sample_rate = Parameter('sample rate', EnumType(slow=0, fast=1), readonly=False)

        ...

        Status = Readable.Status

        # conversion of the code from the CCU4 parameter 'hsf'
        STATUS_MAP = {
            0: (Status.IDLE, 'sensor ok'),
            1: (Status.ERROR, 'sensor warm'),
            2: (Status.ERROR, 'no sensor'),
            3: (Status.ERROR, 'timeout'),
            4: (Status.ERROR, 'not yet read'),
            5: (Status.DISABLED, 'disabled'),
        }

        def read_status(self):
            name, txtvalue = self.communicate('hsf').split('=')
            assert name == 'hsf'
            return self.STATUS_MAP(int(txtvalue))

        def read_empty_length(self):
            name, txtvalue = self.communicate('hem').split('=')
            assert name == 'hem'
            return float(txtvalue)

        def write_empty_length(self, value):
            name, txtvalue = self.communicate('hem=%g' % value).split('=')
            assert name == 'hem'
            return float(txtvalue)

    ...


Here we start to realize, that we will repeat similar code for other parameters,
which means it might be worth to create a *query* method, and then the
*read_<param>* and *write_<param>* methods will become shorter:

.. code:: python

    ...

    class HeLevel(Readable):

        ...


        def query(self, cmd):
            """send a query and get the response

            :param cmd: the name of the parameter to query or '<parameter>=<value'
                        for changing a parameter
            :returns: the (new) value of the parameter
            """
            name, txtvalue = self.communicate(cmd).split('=')
            assert name == cmd.split('=')[0]  # check that we got a reply to our command
            return float(txtvalue)

        def read_value(self):
            return self.query('h')

        def read_status(self):
            return self.STATUS_MAP[int(self.query('hsf'))]

        def read_empty_length(self):
            return self.query('hem')

        def write_empty_length(self, value):
            return self.query('hem=%g' % value)

        def read_full_length(self):
            return self.query('hfu')

        def write_full_length(self, value):
            return self.query('hfu=%g' % value)

        def read_sample_rate(self):
            return self.query('hf')

        def write_sample_rate(self, value):
            return self.query('hf=%d' % value)


:Note:

    It make sense to unify *empty_length* and *full_length* to one parameter *calibration*,
    as a :class:`frappy.datatypes.StructOf` with members *empty_length* and *full_length*:

    .. code:: python

        calibration = Parameter(
            'sensor calibration',
            StructOf(empty_length=FloatRange(0, 2000, unit='mm'),
                     full_length=FloatRange(0, 2000, unit='mm')),
            readonly=False)

    For simplicity we stay with two float parameters for this tutorial.


The full documentation of the example can be found here: :class:`frappy_psi.ccu4.HeLevel`


Configuration
-------------
Before we continue coding, we may try out what we have coded and create a configuration file.
The directory tree of the Frappy framework contains the code for all drivers, but the
configuration file determines, which code will be loaded when a server is started.
We choose the name *example_cryo* and create therefore a configuration file
*example_cryo_cfg.py* in the *cfg* subdirectory:

``cfg/example_cryo_cfg.py``:

.. code:: python

    Node('example_cryo.psi.ch',
         'this is an example cryostat for the Frappy tutorial',
          interface='tcp://5000')
    Mod('helev',
        'frappy_psi.ccu4.HeLevel',
        'He level of the cryostat He reservoir',
        uri='linse-moxa-4.psi.ch:3001',
        empty_length=380,
        full_length=0)

A configuration file contains a node configuration and one or several module configurations.

*Node* describes the main properties of the SEC Node: an id and a description of the node
which should be globally unique, and an interface defining the address of the server,
usually the only important value here is the TCP port under which the server will be accessible.
Currently only tcp is supported.

All the other sections define the SECoP modules to be used. This first arguments of *Mod(* are:

* the module name
* the python class to be used for the creation of the module
* a human readable description is its

Other properties or parameter values may follow, in this case the *uri* for the communication
with the He level monitor and the values for configuring the He Level sensor.
We might also alter parameter properties, for example we may hide
the parameters *empty_length* and *full_length* from the client by defining:

.. code:: python

    Mod('helev',
        'frappy_psi.ccu4.HeLevel',
        'He level of the cryostat He reservoir',
        uri='linse-moxa-4.psi.ch:3001',
        empty_length=Param(380, export=False),
        full_length=Param(0, export=False))

As we configure more than just an initial value, we have to call *Param* and give the
value as the first argument, and additional properties as keyworded arguments.

*to be continued*
