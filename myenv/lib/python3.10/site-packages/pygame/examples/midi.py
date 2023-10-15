#!/usr/bin/env python
""" pygame.examples.midi

midi input, and a separate example of midi output.

By default it runs the output example.

python -m pygame.examples.midi --output
python -m pygame.examples.midi --input
python -m pygame.examples.midi --input
"""

import sys
import os
from typing import Any, Dict, List, Optional, Set, Tuple, Union

import pygame as pg
import pygame.midi

# black and white piano keys use b/w color values directly
BACKGROUNDCOLOR = "slategray"


def print_device_info():
    pygame.midi.init()
    _print_device_info()
    pygame.midi.quit()


def _print_device_info():
    for i in range(pygame.midi.get_count()):
        r = pygame.midi.get_device_info(i)
        (interf, name, input, output, opened) = r

        in_out = ""
        if input:
            in_out = "(input)"
        if output:
            in_out = "(output)"

        print(
            "%2i: interface :%s:, name :%s:, opened :%s:  %s"
            % (i, interf, name, opened, in_out)
        )


def input_main(device_id=None):
    pg.init()

    pygame.midi.init()

    _print_device_info()

    if device_id is None:
        input_id = pygame.midi.get_default_input_id()
    else:
        input_id = device_id

    print(f"using input_id :{input_id}:")
    i = pygame.midi.Input(input_id)

    pg.display.set_mode((1, 1))

    going = True
    while going:
        events = pygame.event.get()
        for e in events:
            if e.type in [pg.QUIT]:
                going = False
            if e.type in [pg.KEYDOWN]:
                going = False
            if e.type in [pygame.midi.MIDIIN]:
                print(e)

        if i.poll():
            midi_events = i.read(10)
            # convert them into pygame events.
            midi_evs = pygame.midi.midis2events(midi_events, i.device_id)

            for m_e in midi_evs:
                pygame.event.post(m_e)

    del i
    pygame.midi.quit()


def output_main(device_id=None):
    """Execute a musical keyboard example for the Church Organ instrument

    This is a piano keyboard example, with a two octave keyboard, starting at
    note F3. Left mouse down over a key starts a note, left up stops it. The
    notes are also mapped to the computer keyboard keys, assuming an American
    English PC keyboard (sorry everyone else, but I don't know if I can map to
    absolute key position instead of value.) The white keys are on the second
    row, TAB to BACKSLASH, starting with note F3. The black keys map to the top
    row, '1' to BACKSPACE, starting with F#3. 'r' is middle C. Close the
    window or press ESCAPE to quit the program. Key velocity (note
    amplitude) varies vertically on the keyboard image, with minimum velocity
    at the top of a key and maximum velocity at bottom.

    Default Midi output, no device_id given, is to the default output device
    for the computer.

    """

    # A note to new pygamers:
    #
    # All the midi module stuff is in this function. It is unnecessary to
    # understand how the keyboard display works to appreciate how midi
    # messages are sent.

    # The keyboard is drawn by a Keyboard instance. This instance maps Midi
    # notes to musical keyboard keys. A regions surface maps window position
    # to (Midi note, velocity) pairs. A key_mapping dictionary does the same
    # for computer keyboard keys. Midi sound is controlled with direct method
    # calls to a pygame.midi.Output instance.
    #
    # Things to consider when using pygame.midi:
    #
    # 1) Initialize the midi module with a to pygame.midi.init().
    # 2) Create a midi.Output instance for the desired output device port.
    # 3) Select instruments with set_instrument() method calls.
    # 4) Play notes with note_on() and note_off() method calls.
    # 5) Call pygame.midi.Quit() when finished. Though the midi module tries
    #    to ensure that midi is properly shut down, it is best to do it
    #    explicitly. A try/finally statement is the safest way to do this.
    #

    # GRAND_PIANO = 0
    CHURCH_ORGAN = 19

    instrument = CHURCH_ORGAN
    # instrument = GRAND_PIANO
    start_note = 53  # F3 (white key note), start_note != 0
    n_notes = 24  # Two octaves (14 white keys)

    key_mapping = make_key_mapping(
        [
            pg.K_TAB,
            pg.K_1,
            pg.K_q,
            pg.K_2,
            pg.K_w,
            pg.K_3,
            pg.K_e,
            pg.K_r,
            pg.K_5,
            pg.K_t,
            pg.K_6,
            pg.K_y,
            pg.K_u,
            pg.K_8,
            pg.K_i,
            pg.K_9,
            pg.K_o,
            pg.K_0,
            pg.K_p,
            pg.K_LEFTBRACKET,
            pg.K_EQUALS,
            pg.K_RIGHTBRACKET,
            pg.K_BACKSPACE,
            pg.K_BACKSLASH,
        ],
        start_note,
    )

    pg.init()
    pygame.midi.init()

    _print_device_info()

    if device_id is None:
        port = pygame.midi.get_default_output_id()
    else:
        port = device_id

    print(f"using output_id :{port}:")

    midi_out = pygame.midi.Output(port, 0)
    try:
        midi_out.set_instrument(instrument)
        keyboard = Keyboard(start_note, n_notes)

        screen = pg.display.set_mode(keyboard.rect.size)
        screen.fill(BACKGROUNDCOLOR)
        pg.display.flip()

        background = pg.Surface(screen.get_size())
        background.fill(BACKGROUNDCOLOR)
        dirty_rects = []
        keyboard.draw(screen, background, dirty_rects)
        pg.display.update(dirty_rects)

        regions = pg.Surface(screen.get_size())  # initial color (0,0,0)
        keyboard.map_regions(regions)

        pg.event.set_blocked(pg.MOUSEMOTION)
        mouse_note = 0
        on_notes = set()
        while True:
            e = pg.event.wait()
            if e.type == pg.MOUSEBUTTONDOWN:
                mouse_note, velocity, __, __ = regions.get_at(e.pos)
                if mouse_note and mouse_note not in on_notes:
                    keyboard.key_down(mouse_note)
                    midi_out.note_on(mouse_note, velocity)
                    on_notes.add(mouse_note)
                else:
                    mouse_note = 0
            elif e.type == pg.MOUSEBUTTONUP:
                if mouse_note:
                    midi_out.note_off(mouse_note)
                    keyboard.key_up(mouse_note)
                    on_notes.remove(mouse_note)
                    mouse_note = 0
            elif e.type == pg.QUIT:
                break
            elif e.type == pg.KEYDOWN:
                if e.key == pg.K_ESCAPE:
                    break
                try:
                    note, velocity = key_mapping[e.key]
                except KeyError:
                    pass
                else:
                    if note not in on_notes:
                        keyboard.key_down(note)
                        midi_out.note_on(note, velocity)
                        on_notes.add(note)
            elif e.type == pg.KEYUP:
                try:
                    note, __ = key_mapping[e.key]
                except KeyError:
                    pass
                else:
                    if note in on_notes and note != mouse_note:
                        keyboard.key_up(note)
                        midi_out.note_off(note, 0)
                        on_notes.remove(note)

            dirty_rects = []
            keyboard.draw(screen, background, dirty_rects)
            pg.display.update(dirty_rects)
    finally:
        del midi_out
        pygame.midi.quit()


def make_key_mapping(keys, start_note):
    """Return a dictionary of (note, velocity) by computer keyboard key code"""
    mapping = {}
    for i, key in enumerate(keys):
        mapping[key] = (start_note + i, 127)
    return mapping


class NullKey:
    """A dummy key that ignores events passed to it by other keys

    A NullKey instance is the left key instance used by default
    for the left most keyboard key.

    """

    def _right_white_down(self):
        pass

    def _right_white_up(self):
        pass

    def _right_black_down(self):
        pass

    def _right_black_up(self):
        pass


null_key = NullKey()


def key_class(updates, image_strip, image_rects: List[pg.Rect], is_white_key=True):
    """Return a keyboard key widget class

    Arguments:
    updates - a set into which a key instance adds itself if it needs
        redrawing.
    image_strip - The surface containing the images of all key states.
    image_rects - A list of Rects giving the regions within image_strip that
        are relevant to this key class.
    is_white_key (default True) - Set false if this is a black key.

    This function automates the creation of a key widget class for the
    three basic key types. A key has two basic states, up or down (
    depressed). Corresponding up and down images are drawn for each
    of these two states. But to give the illusion of depth, a key
    may have shadows cast upon it by the adjacent keys to its right.
    These shadows change depending on the up/down state of the key and
    its neighbors. So a key may support multiple images and states
    depending on the shadows. A key type is determined by the length
    of image_rects and the value of is_white.

    """

    # Naming convention: Variables used by the Key class as part of a
    # closure start with 'c_'.

    # State logic and shadows:
    #
    # A key may cast a shadow upon the key to its left. A black key casts a
    # shadow on an adjacent white key. The shadow changes depending of whether
    # the black or white key is depressed. A white key casts a shadow on the
    # white key to its left if it is up and the left key is down. Therefore
    # a keys state, and image it will draw, is determined entirely by its
    # itself and the key immediately adjacent to it on the right. A white key
    # is always assumed to have an adjacent white key.
    #
    # There can be up to eight key states, representing all permutations
    # of the three fundamental states of self up/down, adjacent white
    # right up/down, adjacent black up/down.
    #
    down_state_none = 0
    down_state_self = 1
    down_state_white = down_state_self << 1
    down_state_self_white = down_state_self | down_state_white
    down_state_black = down_state_white << 1
    down_state_self_black = down_state_self | down_state_black
    down_state_white_black = down_state_white | down_state_black
    down_state_all = down_state_self | down_state_white_black

    # Some values used in the class.
    #
    c_down_state_initial = down_state_none
    c_down_state_rect_initial = image_rects[0]
    c_updates = updates
    c_image_strip = image_strip
    c_width, c_height = image_rects[0].size

    # A key propagates its up/down state change to the adjacent white key on
    # the left by calling the adjacent key's _right_black_down or
    # _right_white_down method.
    #
    if is_white_key:
        key_color = "white"
    else:
        key_color = "black"
    c_notify_down_method = f"_right_{key_color}_down"
    c_notify_up_method = f"_right_{key_color}_up"

    # Images:
    #
    # A black key only needs two images, for the up and down states. Its
    # appearance is unaffected by the adjacent keys to its right, which cast no
    # shadows upon it.
    #
    # A white key with a no adjacent black to its right only needs three
    # images, for self up, self down, and both self and adjacent white down.
    #
    # A white key with both a black and white key to its right needs six
    # images: self up, self up and adjacent black down, self down, self and
    # adjacent white down, self and adjacent black down, and all three down.
    #
    # Each 'c_event' dictionary maps the current key state to a new key state,
    # along with corresponding image, for the related event. If no redrawing
    # is required for the state change then the image rect is simply None.
    #
    c_event_down: Dict[int, Tuple[int, pygame.Rect]] = {
        down_state_none: (down_state_self, image_rects[1])
    }
    c_event_up: Dict[int, Tuple[int, pygame.Rect]] = {
        down_state_self: (down_state_none, image_rects[0])
    }
    c_event_right_white_down: Dict[int, Tuple[int, Union[pygame.Rect, None]]] = {
        down_state_none: (down_state_none, None),
        down_state_self: (down_state_self, None),
    }
    c_event_right_white_up = c_event_right_white_down.copy()
    c_event_right_black_down = c_event_right_white_down.copy()
    c_event_right_black_up = c_event_right_white_down.copy()
    if len(image_rects) > 2:
        c_event_down[down_state_white] = (down_state_self_white, image_rects[2])
        c_event_up[down_state_self_white] = (down_state_white, image_rects[0])
        c_event_right_white_down[down_state_none] = (down_state_white, None)
        c_event_right_white_down[down_state_self] = (
            down_state_self_white,
            image_rects[2],
        )
        c_event_right_white_up[down_state_white] = (down_state_none, None)
        c_event_right_white_up[down_state_self_white] = (
            down_state_self,
            image_rects[1],
        )
        c_event_right_black_down[down_state_white] = (down_state_white, None)
        c_event_right_black_down[down_state_self_white] = (down_state_self_white, None)
        c_event_right_black_up[down_state_white] = (down_state_white, None)
        c_event_right_black_up[down_state_self_white] = (down_state_self_white, None)
    if len(image_rects) > 3:
        c_event_down[down_state_black] = (down_state_self_black, image_rects[4])
        c_event_down[down_state_white_black] = (down_state_all, image_rects[5])
        c_event_up[down_state_self_black] = (down_state_black, image_rects[3])
        c_event_up[down_state_all] = (down_state_white_black, image_rects[3])
        c_event_right_white_down[down_state_black] = (down_state_white_black, None)
        c_event_right_white_down[down_state_self_black] = (
            down_state_all,
            image_rects[5],
        )
        c_event_right_white_up[down_state_white_black] = (down_state_black, None)
        c_event_right_white_up[down_state_all] = (down_state_self_black, image_rects[4])
        c_event_right_black_down[down_state_none] = (down_state_black, image_rects[3])
        c_event_right_black_down[down_state_self] = (
            down_state_self_black,
            image_rects[4],
        )
        c_event_right_black_down[down_state_white] = (
            down_state_white_black,
            image_rects[3],
        )
        c_event_right_black_down[down_state_self_white] = (
            down_state_all,
            image_rects[5],
        )
        c_event_right_black_up[down_state_black] = (down_state_none, image_rects[0])
        c_event_right_black_up[down_state_self_black] = (
            down_state_self,
            image_rects[1],
        )
        c_event_right_black_up[down_state_white_black] = (
            down_state_white,
            image_rects[0],
        )
        c_event_right_black_up[down_state_all] = (down_state_self_white, image_rects[2])

    class Key:
        """A key widget, maintains key state and draws the key's image

        Constructor arguments:
        ident - A unique key identifier. Any immutable type suitable as a key.
        posn - The location of the key on the display surface.
        key_left - Optional, the adjacent white key to the left. Changes in
            up and down state are propagated to that key.

        A key has an associated position and state. Related to state is the
        image drawn. State changes are managed with method calls, one method
        per event type. The up and down event methods are public. Other
        internal methods are for passing on state changes to the key_left
        key instance.

        """

        is_white = is_white_key

        def __init__(self, ident, posn, key_left=None):
            """Return a new Key instance

            The initial state is up, with all adjacent keys to the right also
            up.

            """
            if key_left is None:
                key_left = null_key
            rect = pg.Rect(posn[0], posn[1], c_width, c_height)
            self.rect = rect
            self._state = c_down_state_initial
            self._source_rect = c_down_state_rect_initial
            self._ident = ident
            self._hash = hash(ident)
            self._notify_down = getattr(key_left, c_notify_down_method)
            self._notify_up = getattr(key_left, c_notify_up_method)
            self._key_left = key_left
            self._background_rect = pg.Rect(rect.left, rect.bottom - 10, c_width, 10)
            c_updates.add(self)

        def down(self):
            """Signal that this key has been depressed (is down)"""

            self._state, source_rect = c_event_down[self._state]
            if source_rect is not None:
                self._source_rect = source_rect
                c_updates.add(self)
                self._notify_down()

        def up(self):
            """Signal that this key has been released (is up)"""

            self._state, source_rect = c_event_up[self._state]
            if source_rect is not None:
                self._source_rect = source_rect
                c_updates.add(self)
                self._notify_up()

        def _right_white_down(self):
            """Signal that the adjacent white key has been depressed

            This method is for internal propagation of events between
            key instances.

            """

            self._state, source_rect = c_event_right_white_down[self._state]
            if source_rect is not None:
                self._source_rect = source_rect
                c_updates.add(self)

        def _right_white_up(self):
            """Signal that the adjacent white key has been released

            This method is for internal propagation of events between
            key instances.

            """

            self._state, source_rect = c_event_right_white_up[self._state]
            if source_rect is not None:
                self._source_rect = source_rect
                c_updates.add(self)

        def _right_black_down(self):
            """Signal that the adjacent black key has been depressed

            This method is for internal propagation of events between
            key instances.

            """

            self._state, source_rect = c_event_right_black_down[self._state]
            if source_rect is not None:
                self._source_rect = source_rect
                c_updates.add(self)

        def _right_black_up(self):
            """Signal that the adjacent black key has been released

            This method is for internal propagation of events between
            key instances.

            """

            self._state, source_rect = c_event_right_black_up[self._state]
            if source_rect is not None:
                self._source_rect = source_rect
                c_updates.add(self)

        def __eq__(self, other):
            """True if same identifiers"""

            return self._ident == other._ident

        def __hash__(self):
            """Return the immutable hash value"""

            return self._hash

        def __str__(self):
            """Return the key's identifier and position as a string"""

            return "<Key %s at (%d, %d)>" % (self._ident, self.rect.top, self.rect.left)

        def draw(self, surf, background, dirty_rects):
            """Redraw the key on the surface surf

            The background is redrawn. The altered region is added to the
            dirty_rects list.

            """

            surf.blit(background, self._background_rect, self._background_rect)
            surf.blit(c_image_strip, self.rect, self._source_rect)
            dirty_rects.append(self.rect)

    return Key


def key_images() -> Tuple[pg.Surface, Dict[str, pg.Rect]]:
    """Return a keyboard keys image strip and a mapping of image locations

    The return tuple is a pygame.Surface and a dictionary keyed by key name and valued by a pygame.Rect.

    This function encapsulates the constants relevant to the keyboard image
    file. There are five key types. One is the black key. The other four
    white keys are determined by the proximity of the black keys. The plain
    white key has no black key adjacent to it. A white-left and white-right
    key has a black key to the left or right of it respectively. A white-center
    key has a black key on both sides. A key may have up to six related
    images depending on the state of adjacent keys to its right.

    """

    my_dir = os.path.split(os.path.abspath(__file__))[0]
    strip_file = os.path.join(my_dir, "data", "midikeys.png")
    white_key_width = 42
    white_key_height = 160
    black_key_width = 22
    black_key_height = 94
    strip = pg.image.load(strip_file)
    names = [
        "black none",
        "black self",
        "white none",
        "white self",
        "white self-white",
        "white-left none",
        "white-left self",
        "white-left black",
        "white-left self-black",
        "white-left self-white",
        "white-left all",
        "white-center none",
        "white-center self",
        "white-center black",
        "white-center self-black",
        "white-center self-white",
        "white-center all",
        "white-right none",
        "white-right self",
        "white-right self-white",
    ]
    rects = {}
    for i in range(2):
        rects[names[i]] = pg.Rect(
            i * white_key_width, 0, black_key_width, black_key_height
        )
    for i in range(2, len(names)):
        rects[names[i]] = pg.Rect(
            i * white_key_width, 0, white_key_width, white_key_height
        )
    return strip, rects


class Keyboard:
    """Musical keyboard widget

    Constructor arguments:
    start_note: midi note value of the starting note on the keyboard.
    n_notes: number of notes (keys) on the keyboard.

    A Keyboard instance draws the musical keyboard and maintains the state of
    all the keyboard keys. Individual keys can be in a down (depressed) or
    up (released) state.

    """

    _image_strip, _rects = key_images()

    white_key_width, white_key_height = _rects["white none"].size
    black_key_width, black_key_height = _rects["black none"].size

    _updates: Set[Any] = set()

    # There are five key classes, representing key shape:
    # black key (BlackKey), plain white key (WhiteKey), white key to the left
    # of a black key (WhiteKeyLeft), white key between two black keys
    # (WhiteKeyCenter), and white key to the right of a black key
    # (WhiteKeyRight).
    BlackKey = key_class(
        _updates, _image_strip, [_rects["black none"], _rects["black self"]], False
    )
    WhiteKey = key_class(
        _updates,
        _image_strip,
        [_rects["white none"], _rects["white self"], _rects["white self-white"]],
    )
    WhiteKeyLeft = key_class(
        _updates,
        _image_strip,
        [
            _rects["white-left none"],
            _rects["white-left self"],
            _rects["white-left self-white"],
            _rects["white-left black"],
            _rects["white-left self-black"],
            _rects["white-left all"],
        ],
    )
    WhiteKeyCenter = key_class(
        _updates,
        _image_strip,
        [
            _rects["white-center none"],
            _rects["white-center self"],
            _rects["white-center self-white"],
            _rects["white-center black"],
            _rects["white-center self-black"],
            _rects["white-center all"],
        ],
    )
    WhiteKeyRight = key_class(
        _updates,
        _image_strip,
        [
            _rects["white-right none"],
            _rects["white-right self"],
            _rects["white-right self-white"],
        ],
    )

    def __init__(self, start_note, n_notes):
        """Return a new Keyboard instance with n_note keys"""

        self._start_note = start_note
        self._end_note = start_note + n_notes - 1
        self._add_keys()

    def _add_keys(self):
        """Populate the keyboard with key instances

        Set the _keys and rect attributes.

        """

        # Keys are entered in a list, where index is Midi note. Since there are
        # only 128 possible Midi notes the list length is manageable. Unassigned
        # note positions should never be accessed, so are set None to ensure
        # the bug is quickly detected.
        #
        key_map: list[Any] = [None] * 128

        start_note = self._start_note
        end_note = self._end_note
        black_offset = self.black_key_width // 2
        prev_white_key = None
        x = y = 0
        if is_white_key(start_note):
            is_prev_white = True
        else:
            x += black_offset
            is_prev_white = False
        for note in range(start_note, end_note + 1):
            ident = note  # For now notes uniquely identify keyboard keys.
            if is_white_key(note):
                if is_prev_white:
                    if note == end_note or is_white_key(note + 1):
                        key = self.WhiteKey(ident, (x, y), prev_white_key)
                    else:
                        key = self.WhiteKeyLeft(ident, (x, y), prev_white_key)
                else:
                    if note == end_note or is_white_key(note + 1):
                        key = self.WhiteKeyRight(ident, (x, y), prev_white_key)
                    else:
                        key = self.WhiteKeyCenter(ident, (x, y), prev_white_key)
                is_prev_white = True
                x += self.white_key_width
                prev_white_key = key
            else:
                key = self.BlackKey(ident, (x - black_offset, y), prev_white_key)
                is_prev_white = False
            key_map[note] = key
        self._keys = key_map

        kb_width = key_map[self._end_note].rect.right
        kb_height = self.white_key_height
        self.rect = pg.Rect(0, 0, kb_width, kb_height)

    def map_regions(self, regions):
        """Draw the key regions onto surface regions.

        Regions must have at least 3 byte pixels. Each pixel of the keyboard
        rectangle is set to the color (note, velocity, 0). The regions surface
        must be at least as large as (0, 0, self.rect.left, self.rect.bottom)

        """

        # First draw the white key regions. Then add the overlapping
        # black key regions.
        #
        cutoff = self.black_key_height
        black_keys = []
        for note in range(self._start_note, self._end_note + 1):
            key = self._keys[note]
            if key.is_white:
                fill_region(regions, note, key.rect, cutoff)
            else:
                black_keys.append((note, key))
        for note, key in black_keys:
            fill_region(regions, note, key.rect, cutoff)

    def draw(self, surf, background, dirty_rects):
        """Redraw all altered keyboard keys"""

        changed_keys = self._updates
        while changed_keys:
            changed_keys.pop().draw(surf, background, dirty_rects)

    def key_down(self, note):
        """Signal a key down event for note"""

        self._keys[note].down()

    def key_up(self, note):
        """Signal a key up event for note"""

        self._keys[note].up()


def fill_region(regions, note, rect, cutoff):
    """Fill the region defined by rect with a (note, velocity, 0) color

    The velocity varies from a small value at the top of the region to
    127 at the bottom. The vertical region 0 to cutoff is split into
    three parts, with velocities 42, 84 and 127. Everything below cutoff
    has velocity 127.

    """

    x, y, width, height = rect
    if cutoff is None:
        cutoff = height
    delta_height = cutoff // 3
    regions.fill((note, 42, 0), (x, y, width, delta_height))
    regions.fill((note, 84, 0), (x, y + delta_height, width, delta_height))
    regions.fill(
        (note, 127, 0), (x, y + 2 * delta_height, width, height - 2 * delta_height)
    )


def is_white_key(note):
    """True if note is represented by a white key"""

    key_pattern = [
        True,
        False,
        True,
        True,
        False,
        True,
        False,
        True,
        True,
        False,
        True,
        False,
    ]
    return key_pattern[(note - 21) % len(key_pattern)]


def usage():
    print("--input [device_id] : Midi message logger")
    print("--output [device_id] : Midi piano keyboard")
    print("--list : list available midi devices")


def main(mode="output", device_id=None):
    """Run a Midi example

    Arguments:
    mode - if 'output' run a midi keyboard output example
              'input' run a midi event logger input example
              'list' list available midi devices
           (default 'output')
    device_id - midi device number; if None then use the default midi input or
                output device for the system

    """

    if mode == "input":
        input_main(device_id)
    elif mode == "output":
        output_main(device_id)
    elif mode == "list":
        print_device_info()
    else:
        raise ValueError(f"Unknown mode option '{mode}'")


if __name__ == "__main__":
    device_id: Optional[int] = None
    try:
        device_id = int(sys.argv[-1])
    except ValueError:
        device_id = None

    if "--input" in sys.argv or "-i" in sys.argv:
        input_main(device_id)

    elif "--output" in sys.argv or "-o" in sys.argv:
        output_main(device_id)
    elif "--list" in sys.argv or "-l" in sys.argv:
        print_device_info()
    else:
        usage()

    pg.quit()
