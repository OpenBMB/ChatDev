.. include:: common.txt

:mod:`pygame.context`
======================

.. module:: pygame.context
    :synopsis: pygame module to provide additional context about the system

| :sl:`pygame module to provide additional context about the system`

**EXPERIMENTAL!** This API may change or disappear in later pygame releases. 
If you use this, your code may break with the next pygame release.
This is a new module, so we are marking it experimental for now.
We probably won't have to change API, but we're keeping the possibility
open just in case something obvious comes up.

.. versionadded:: 2.1.3

.. function:: get_pref_path

   | :sl:`get a writeable folder for your app`
   | :sg:`get_pref_path(org, app) -> path`

   When distributing apps, it's helpful to have a way to get a writeable path,
   because it's what apps are expected to do, and because sometimes the local
   space around the app isn't writeable to the app.

   This function returns a platform specific path for your app to store
   savegames, settings, and the like. This path is unique per user and
   per app name.

   It takes two strings, ``org`` and ``app``, referring to the "organization"
   and "application name." For example, the organization could be "Valve," 
   and the application name could be "Half Life 2." It then will figure out the
   preferred path, **creating the folders referenced by the path if necessary**,
   and return a string containing the absolute path.

   For example::

        On Windows, it would resemble
        C:\\Users\\bob\\AppData\\Roaming\\My Company\\My Program Name\\

        On macOS, it would resemble
        /Users/bob/Library/Application Support/My Program Name/

        And on Linux it would resemble
        /home/bob/.local/share/My Program Name/
    
   .. versionadded:: 2.1.3

.. function:: get_pref_locales

   | :sl:`get preferred locales set on the system`
   | :sg:`get_pref_locales() -> list[locale]`

   Returns a list of "locale" dicts, sorted in descending order of preference
   set on the host OS (the most preferred locale is the first element). May
   also be an empty list if pygame could not find this information.

   Each "locale" dict contains the language code which can be accessed by the
   key ``"language"``. This language code is an ISO-639 language specifier 
   (such as "en" for English, "de" for German, etc).
   A "locale" dict may also optionally contain a ``"country"`` field, whose
   value is an ISO-3166 country code (such as "US" for the United States, 
   "CA" for Canada, etc). If this field is not set or undetermined, it is 
   ``None``.
   A "locale" dict which looks like ``{'language': 'en', 'country': 'US'}``
   indicates the user prefers American English, while
   ``{'language': 'en', 'country': None}`` indicates that the user prefers
   English, generically.

   This might be a bit of an expensive call because it has to query the OS. So
   this function must not be called in a game loop, instead it's best to ask 
   for this once and save the results. However, this list can change when the
   user changes a system preference outside of your program. pygame will send
   a ``LOCALECHANGED`` event in this case, if possible, and you can call this
   function again to get an updated copy of preferred locales.

   .. note::
        Since the organization and app names can potentially be used as
        a folder name, it is highly encouraged to avoid punctuation.
        Instead stick to letters, numbers, and spaces.

   .. note::
        The ``appdirs`` library has similar functionality for this use case,
        but has more "folder types" to choose from.

   .. versionadded:: 2.1.3
