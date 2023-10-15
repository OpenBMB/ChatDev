.. include:: common.txt

:mod:`pygame._sdl2.controller`
==============================

.. module:: pygame._sdl2.controller
   :synopsis: pygame module to work with controllers

| :sl:`Pygame module to work with controllers.`

This module offers control over common controller types like the dualshock 4 or
the xbox 360 controllers: They have two analog sticks, two triggers, two shoulder buttons,
a dpad, 4 buttons on the side, 2 (or 3) buttons in the middle.

Pygame uses xbox controllers naming conventions (like a, b, x, y for buttons) but
they always refer to the same buttons. For example ``CONTROLLER_BUTTON_X`` is
always the leftmost button of the 4 buttons on the right.

Controllers can generate the following events::

   CONTROLLERAXISMOTION, CONTROLLERBUTTONDOWN, CONTROLLERBUTTONUP,
   CONTROLLERDEVICEREMAPPED, CONTROLLERDEVICEADDED, CONTROLLERDEVICEREMOVED

Additionally if pygame is built with SDL 2.0.14 or higher the following events can also be generated
(to get the version of sdl pygame is built with use :meth:`pygame.version.SDL`)::

   CONTROLLERTOUCHPADDOWN, CONTROLLERTOUCHPADMOTION, CONTROLLERTOUCHPADUP

These events can be enabled/disabled by :meth:`pygame._sdl2.controller.set_eventstate`
Note that controllers can generate joystick events as well. This function only toggles
events related to controllers.

.. note::
   See the :mod:`pygame.joystick` for a more versatile but more advanced api.

.. versionadded:: 2 This module requires SDL2.

.. function:: init

   | :sl:`initialize the controller module`
   | :sg:`init() -> None`

   Initialize the controller module.

   .. ## pygame._sdl2.controller.init ##

.. function:: quit

   | :sl:`Uninitialize the controller module.`
   | :sg:`quit() -> None`

   Uninitialize the controller module.

   .. ## pygame._sdl2.controller.quit ##

.. function:: get_init

   | :sl:`Returns True if the controller module is initialized.`
   | :sg:`get_init() -> bool`

   Test if ``pygame._sdl2.controller.init()`` was called.

    .. ## pygame._sdl2.controller.get_init ##

.. function:: set_eventstate

    | :sl:`Sets the current state of events related to controllers`
    | :sg:`set_eventstate(state) -> None`

    Enable or disable events connected to controllers.

    .. note::
        Controllers can still generate joystick events, which will not be toggled by this function.

    .. versionchanged:: 2.0.2: Changed return type from int to None

    .. ## pygame._sdl2.controller.set_eventstate ##

.. function:: get_eventstate

    | :sl:`Gets the current state of events related to controllers`
    | :sg:`get_eventstate() -> bool`

    Returns the current state of events related to controllers, True meaning
    events will be posted.

    .. versionadded:: 2.0.2

    .. ## pygame._sdl2.controller.get_eventstate ##

.. function:: get_count

    | :sl:`Get the number of joysticks connected`
    | :sg:`get_count() -> int`

    Get the number of joysticks connected.

    .. ## pygame._sdl2.controller.get_count ##

.. function:: is_controller

    | :sl:`Check if the given joystick is supported by the game controller interface`
    | :sg:`is_controller(index) -> bool`

    Returns True if the index given can be used to create a controller object.

    .. ## pygame._sdl2.controller.is_controller ##

.. function:: name_forindex

    | :sl:`Get the name of the controller`
    | :sg:`name_forindex(index) -> name or None`

    Returns the name of controller, or None if there's no name or the
    index is invalid.

    .. ## pygame._sdl2.controller.name_forindex ##

.. class:: Controller

    | :sl:`Create a new Controller object.`
    | :sg:`Controller(index) -> Controller`

    Create a new Controller object. Index should be integer between
    0 and ``pygame._sdl2.controller.get_count()``. Controllers also
    can be created from a ``pygame.joystick.Joystick`` using
    ``pygame._sdl2.controller.from_joystick``. Controllers are
    initialized on creation.

   .. method:: quit

      | :sl:`uninitialize the Controller`
      | :sg:`quit() -> None`

      Close a Controller object. After this the pygame event queue will no longer
      receive events from the device.

      It is safe to call this more than once.

      .. ## Controller.quit ##

   .. method:: get_init

      | :sl:`check if the Controller is initialized`
      | :sg:`get_init() -> bool`

      Returns True if the Controller object is currently initialised.

      .. ## Controller.get_init ##

   .. staticmethod:: from_joystick

       | :sl:`Create a Controller from a pygame.joystick.Joystick object`
       | :sg:`from_joystick(joystick) -> Controller`

       Create a Controller object from a ``pygame.joystick.Joystick`` object

       .. ## Controller.from_joystick ##

   .. method:: attached

      | :sl:`Check if the Controller has been opened and is currently connected.`
      | :sg:`attached() -> bool`

      Returns True if the Controller object is opened and connected.

      .. ## Controller.attached ##

   .. method:: as_joystick

      | :sl:`Returns a pygame.joystick.Joystick() object`
      | :sg:`as_joystick() -> Joystick object`

      Returns a pygame.joystick.Joystick() object created from this controller's index

      .. ## Controller.as_joystick ##

   .. method:: get_axis

      | :sl:`Get the current state of a joystick axis`
      | :sg:`get_axis(axis) -> int`

      Get the current state of a trigger or joystick axis.
      The axis argument must be one of the following constants::

         CONTROLLER_AXIS_LEFTX, CONTROLLER_AXIS_LEFTY,
         CONTROLLER_AXIS_RIGHTX, CONTROLLER_AXIS_RIGHTY,
         CONTROLLER_AXIS_TRIGGERLEFT, CONTROLLER_AXIS_TRIGGERRIGHT

      Joysticks can return a value between -32768 and 32767. Triggers however
      can only return a value between 0 and 32768.

      .. ## Controller.get_axis ##

   .. method:: get_button

      | :sl:`Get the current state of a button`
      | :sg:`get_button(button) -> bool`

      Get the current state of a button, True meaning it is pressed down.
      The button argument must be one of the following constants::

         CONTROLLER_BUTTON_A, CONTROLLER_BUTTON_B,
         CONTROLLER_BUTTON_X, CONTROLLER_BUTTON_Y
         CONTROLLER_BUTTON_DPAD_UP, CONTROLLER_BUTTON_DPAD_DOWN,
         CONTROLLER_BUTTON_DPAD_LEFT, CONTROLLER_BUTTON_DPAD_RIGHT,
         CONTROLLER_BUTTON_LEFTSHOULDER, CONTROLLER_BUTTON_RIGHTSHOULDER,
         CONTROLLER_BUTTON_LEFTSTICK, CONTROLLER_BUTTON_RIGHTSTICK,
         CONTROLLER_BUTTON_BACK, CONTROLLER_BUTTON_GUIDE,
         CONTROLLER_BUTTON_START


      .. ## Controller.get_button ##

   .. method:: get_mapping

      | :sl:`Get the mapping assigned to the controller`
      | :sg:`get_mapping() -> mapping`

      Returns a dict containing the mapping of the Controller. For more
      information see :meth:`Controller.set_mapping()`

      .. versionchanged:: 2.0.2: Return type changed from ``str`` to ``dict``

      .. ## Contorller.get_mapping ##

   .. method:: set_mapping

      | :sl:`Assign a mapping to the controller`
      | :sg:`set_mapping(mapping) -> int`

      Rebind buttons, axes, triggers and dpads. The mapping should be a 
      dict containing all buttons, hats and axes. The easiest way to get this
      is to use the dict returned by :meth:`Controller.get_mapping`. To edit
      this mapping assign a value to the original button. The value of the
      dictionary must be a button, hat or axis represented in the following way:

      * For a button use: bX where X is the index of the button.
      * For a hat use: hX.Y where X is the index and the Y is the direction (up: 1, right: 2, down: 3, left: 4).
      * For an axis use: aX where x is the index of the axis.

      An example of mapping::

         mapping = controller.get_mapping() # Get current mapping
         mapping["a"] = "b3" # Remap button a to y
         mapping["y"] = "b0" # Remap button y to a
         controller.set_mapping(mapping) # Set the mapping


      The function will return 1 if a new mapping is added or 0 if an existing one is updated.

      .. versionchanged:: 2.0.2: Renamed from ``add_mapping`` to ``set_mapping``
      .. versionchanged:: 2.0.2: Argument type changed from ``str`` to ``dict``

      .. ## Contorller.set_mapping ##

   .. method:: rumble

      | :sl:`Start a rumbling effect`
      | :sg:`rumble(low_frequency, high_frequency, duration) -> bool`

      Start a rumble effect on the controller, with the specified strength ranging
      from 0 to 1. Duration is length of the effect, in ms. Setting the duration
      to 0 will play the effect until another one overwrites it or
      :meth:`Controller.stop_rumble` is called. If an effect is already
      playing, then it will be overwritten.

      Returns True if the rumble was played successfully or False if the
      controller does not support it or :meth:`pygame.version.SDL` is below 2.0.9.

      .. versionadded:: 2.0.2

      .. ## Contorller.rumble ##

   .. method:: stop_rumble

      | :sl:`Stop any rumble effect playing`
      | :sg:`stop_rumble() -> None`

      Stops any rumble effect playing on the controller. See
      :meth:`Controller.rumble` for more information.

      .. versionadded:: 2.0.2

      .. ## Contorller.stop_rumble ##

.. ## pygame._sdl2.controller ##
