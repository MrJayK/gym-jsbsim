import jsbsim
import os
import time
from mpl_toolkits.mplot3d import Axes3D  # req'd for 3d plotting
from typing import Dict, TYPE_CHECKING
from gym_jsbsim.properties import InitialProperty


class Simulation(object):
    """
    A class which wraps an instance of JSBSim and manages communication with it.
    """
    encoding = 'utf-8'  # encoding of bytes returned by JSBSim Cython funcs
    ROOT_DIR = os.path.abspath('/home/gordon/apps/jsbsim')
    OUTPUT_FILE = 'flightgear.xml'
    LONGITUDINAL = 'longitudinal'
    FULL = 'full'

    def __init__(self,
                 sim_frequency_hz: float=60.0,
                 aircraft_model_name: str='c172p',
                 init_conditions: Dict['InitialProperty', float]=None,
                 allow_flightgear_output: bool=True):
        """
        Constructor. Creates an instance of JSBSim and sets initial conditions.

        :param sim_frequency_hz: float, the JSBSim integration frequency in Hz.
        :param aircraft_model_name: string, name of aircraft to be loaded.
            JSBSim looks for file \model_name\model_name.xml from root dir.
        :param init_conditions: dict mapping properties to their initial values.
            Defaults to None, causing a default set of initial props to be used.
        :param allow_flightgear_output: bool, loads a config file instructing
            JSBSim to connect to an output socket if True.
        """
        self.jsbsim = jsbsim.FGFDMExec(root_dir=self.ROOT_DIR)
        self.jsbsim.set_debug_level(0)
        if allow_flightgear_output:
            flightgear_output_config = os.path.join(os.path.dirname(os.path.abspath(__file__)), self.OUTPUT_FILE)
            self.jsbsim.set_output_directive(flightgear_output_config)
        self.sim_dt = 1.0 / sim_frequency_hz
        self.initialise(self.sim_dt, aircraft_model_name, init_conditions)
        self.jsbsim.disable_output()
        self.wall_clock_dt = None

    def __getitem__(self, key: str):
        """
        Retrieves specified simulation property.

        Properties are identified by strings. A list can be found in the JSBSim
        reference manual, launching JSBSim with '--catalog' command line arg or
        calling FGFDMExec.get_property_catalog().

        :param key: string, the property to be retrieved
        :return: object?, property value
        :raises KeyError: if key is not a valid parameter
        """
        return self.jsbsim[key]

    def __setitem__(self, key: str, value) -> None:
        """
        Sets simulation property to specified value.

        Properties are identified by strings. A list can be found in the JSBSim
        reference manual, launching JSBSim with '--catalog' command line arg or
        calling FGFDMExec.get_property_catalog().

        Warning: JSBSim will create new properties if the specified one exists.
        If the property you are setting is read-only in JSBSim the operation
        will silently fail.

        :param key: string, the property to be retrieved
        :param value: object?, the value to be set
        :raises KeyError: if key is not a valid parameter
        """
        self.jsbsim[key] = value

    def load_model(self, model_name: str) -> None:
        """
        Loads the specified aircraft config into the simulation.

        The root JSBSim directory aircraft folder is searched for the aircraft
        XML config file.

        :param model_name: string, the aircraft name
        """
        load_success = self.jsbsim.load_model(model_name)

        if not load_success:
            raise RuntimeError('JSBSim could not find specified model_name: '
                               + model_name)

    def get_model_name(self) -> str:
        """
        Gets the name of the aircraft model currently loaded in JSBSim.

        :return: string, the name of the aircraft model if one is loaded, or
            None if no model is loaded.
        """
        name: str = self.jsbsim.get_model_name().decode(self.encoding)
        if name:
            return name
        else:
            # name is empty string, no model is loaded
            return None

    def get_sim_time(self) -> float:
        """ Gets the simulation time from JSBSim, a float. """
        return self.jsbsim['simulation/sim-time-sec']

    def initialise(self, dt: float, model_name: str,
                   init_conditions: Dict['InitialProperty', float]=None) -> None:
        """
        Loads an aircraft and initialises simulation conditions.

        JSBSim creates an InitialConditions object internally when given an
        XML config file. This method either loads a basic set of ICs, or
        can be passed a dictionary with ICs. In the latter case a minimal IC
        XML file is loaded, and then the dictionary values are fed in.

        :param dt: float, the JSBSim integration timestep in seconds
        :param model_name: string, name of aircraft to be loaded
        :param init_conditions: dict mapping properties to their initial values
        """
        if init_conditions is not None:
            # if we are specifying conditions, load a minimal file
            ic_file = 'minimal_ic.xml'
        else:
            ic_file = 'basic_ic.xml'

        ic_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ic_file)
        self.jsbsim.load_ic(ic_path, useStoredPath=False)
        self.load_model(model_name)
        self.jsbsim.set_dt(dt)
        # extract set of legal property names for this aircraft
        # TODO: can remove the .split(" ")[0] once JSBSim bug has been fixed (in progress)

        # now that IC object is created in JSBSim, specify own conditions
        self.set_custom_initial_conditions(init_conditions)

        success = self.jsbsim.run_ic()
        if not success:
            raise RuntimeError('JSBSim failed to init simulation conditions.')

    def set_custom_initial_conditions(self, init_conditions: Dict['InitialProperty', float]=None) -> None:
        if init_conditions is not None:
            for prop, value in init_conditions.items():
                self[prop.name] = value

    def reinitialise(self, init_conditions: Dict['InitialProperty', float]=None) -> None:
        """
        Resets JSBSim to initial conditions.

        The same aircraft and other settings are kept loaded in JSBSim. If a
        dict of ICs is provided, JSBSim is initialised using these, else the
        last specified ICs are used.

        :param init_conditions: dict mapping properties to their initial values
        """
        self.set_custom_initial_conditions(init_conditions=init_conditions)
        no_output_reset_mode = 0
        self.jsbsim.reset_to_initial_conditions(no_output_reset_mode)

    def run(self) -> bool:
        """
        Runs a single timestep in the JSBSim simulation.

        JSBSim monitors the simulation and detects whether it thinks it should
        end, e.g. because a simulation time was specified. False is returned
        if JSBSim termination criteria are met.

        :return: bool, False if sim has met JSBSim termination criteria else True.
        """
        result = self.jsbsim.run()
        if self.wall_clock_dt is not None:
            time.sleep(self.wall_clock_dt)
        return result

    def enable_flightgear_output(self):
        self.jsbsim.enable_output()

    def disable_flightgear_output(self):
        self.jsbsim.disable_output()

    def close(self):
        """ Closes the simulation and any plots. """
        if self.jsbsim:
            self.jsbsim = None

    def set_simulation_time_factor(self, time_factor):
        """
        Specifies a factor, relative to realtime, for simulation to run at.

        The simulation runs at realtime for time_factor = 1. It runs at double
        speed for time_factor=2, and half speed for 0.5.

        :param time_factor: int or float, nonzero, sim speed relative to realtime
            if None, the simulation is run at maximum computational speed
        """
        if time_factor is None:
            self.wall_clock_dt = None
        elif time_factor <= 0:
            raise ValueError('time factor must be positive and non-zero')
        else:
            self.wall_clock_dt = self.sim_dt / time_factor

    def start_engines(self):
        """ Sets all engines running. """
        for engine_no in range(self.jsbsim.propulsion_get_num_engines()):
            self.jsbsim.propulsion_init_running(engine_no)

    def trim(self, trim_mode: str):
        """
        Instructs JSBSim to attempt to trim the aircraft to maintain its ICs

        Valid trim_modes are
            'longitudinal': aircraft's forward velocity, upward velocity and
                pitch rate are controlled to zero by adjusting controls
            'full': as with longitudinal, plus aircraft's sidewards velocity,
                roll rate and yaw rate are controlled to zero

        :param trim_mode: int
        """
        if trim_mode == 'longitudinal':
            trim_code = 0
        elif trim_mode == 'full':
            trim_code = 1
        else:
            raise ValueError(f'invalid trim mode specified: {trim_mode}')

        self.jsbsim.do_trim(trim_code)
