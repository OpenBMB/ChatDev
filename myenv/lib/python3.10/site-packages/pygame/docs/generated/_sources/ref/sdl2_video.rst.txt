.. include:: common.txt

:mod:`pygame.sdl2_video`
========================

.. module:: pygame._sdl2.video
   :synopsis: Experimental pygame module for porting new SDL video systems

.. warning::
	This module isn't ready for prime time yet, it's still in development.
        These docs are primarily meant to help the pygame developers and super-early adopters
        who are in communication with the developers. This API will change.

| :sl:`Experimental pygame module for porting new SDL video systems`

.. class:: Window

   | :sl:`pygame object that represents a window`
   | :sg:`Window(title="pygame", size=(640, 480), position=None, fullscreen=False, fullscreen_desktop=False, keywords) -> Window`

   .. classmethod:: from_display_module
   
      | :sl:`Creates window using window created by pygame.display.set_mode().`
      | :sg:`from_display_module() -> Window`

   .. classmethod:: from_window

      | :sl:`Create Window from another window. Could be from another UI toolkit.`
      | :sg:`from_window(other) -> Window`

   .. attribute:: grab

      | :sl:`Gets or sets whether the mouse is confined to the window.`
      | :sg:`grab -> bool`

   .. attribute:: relative_mouse

      | :sl:`Gets or sets the window's relative mouse motion state.`
      | :sg:`relative_mouse -> bool`

   .. method:: set_windowed

      | :sl:`Enable windowed mode (exit fullscreen).`
      | :sg:`set_windowed() -> None`

   .. method:: set_fullscreen

      | :sl:`Enter fullscreen.`
      | :sg:`set_fullscreen(desktop=False) -> None`

   .. attribute:: title

      | :sl:`Gets or sets whether the window title.`
      | :sg:`title -> string`

   .. method:: destroy

      | :sl:`Destroys the window.`
      | :sg:`destroy() -> None`

   .. method:: hide

      | :sl:`Hide the window.`
      | :sg:`hide() -> None`

   .. method:: show

      | :sl:`Show the window.`
      | :sg:`show() -> None`

   .. method:: focus

      | :sl:`Raise the window above other windows and set the input focus. The "input_only" argument is only supported on X11.`
      | :sg:`focus(input_only=False) -> None`

   .. method:: restore

      | :sl:`Restore the size and position of a minimized or maximized window.`
      | :sg:`restore() -> None`

   .. method:: maximize

      | :sl:`Maximize the window.`
      | :sg:`maximize() -> None`

   .. method:: minimize

      | :sl:`Minimize the window.`
      | :sg:`maximize() -> None`

   .. attribute:: resizable

      | :sl:`Gets and sets whether the window is resizable.`
      | :sg:`resizable -> bool`

   .. attribute:: borderless

      | :sl:`Add or remove the border from the window.`
      | :sg:`borderless -> bool`

   .. method:: set_icon

      | :sl:`Set the icon for the window.`
      | :sg:`set_icon(surface) -> None`

   .. attribute:: id

      | :sl:`Get the unique window ID. *Read-only*`
      | :sg:`id -> int`

   .. attribute:: size

      | :sl:`Gets and sets the window size.`
      | :sg:`size -> (int, int)`

   .. attribute:: position

      | :sl:`Gets and sets the window position.`
      | :sg:`position -> (int, int) or WINDOWPOS_CENTERED or WINDOWPOS_UNDEFINED`	

   .. attribute:: opacity

      | :sl:`Gets and sets the window opacity. Between 0.0 (fully transparent) and 1.0 (fully opaque).`
      | :sg:`opacity -> float`

   .. attribute:: display_index

      | :sl:`Get the index of the display that owns the window. *Read-only*`
      | :sg:`display_index -> int`

   .. method:: set_modal_for

      | :sl:`Set the window as a modal for a parent window. This function is only supported on X11.`
      | :sg:`set_modal_for(Window) -> None`

.. class:: Texture	

   | :sl:`pygame object that representing a Texture.`
   | :sg:`Texture(renderer, size, depth=0, static=False, streaming=False, target=False) -> Texture`

   .. staticmethod:: from_surface

      | :sl:`Create a texture from an existing surface.`
      | :sg:`from_surface(renderer, surface) -> Texture`

   .. attribute:: renderer

      | :sl:`Gets the renderer associated with the Texture. *Read-only*`
      | :sg:`renderer -> Renderer`

   .. attribute:: width

      | :sl:`Gets the width of the Texture. *Read-only*`
      | :sg:`width -> int`

   .. attribute:: height

      | :sl:`Gets the height of the Texture. *Read-only*`
      | :sg:`height -> int`

   .. attribute:: alpha

      | :sl:`Gets and sets an additional alpha value multiplied into render copy operations.`
      | :sg:`alpha -> int`

   .. attribute:: blend_mode

      | :sl:`Gets and sets the blend mode for the Texture.`
      | :sg:`blend_mode -> int`

   .. attribute:: color

      | :sl:`Gets and sets an additional color value multiplied into render copy operations.`
      | :sg:`color -> color`

   .. method:: get_rect

      | :sl:`Get the rectangular area of the texture.`
      | :sg:`get_rect(**kwargs) -> Rect`

   .. method:: draw

      | :sl:`Copy a portion of the texture to the rendering target.`
      | :sg:`draw(srcrect=None, dstrect=None, angle=0, origin=None, flip_x=False, flip_y=False) -> None`

   .. method:: update

      | :sl:`Update the texture with a Surface. WARNING: Slow operation, use sparingly.`
      | :sg:`update(surface, area=None) -> None`

.. class:: Image

   | :sl:`Easy way to use a portion of a Texture without worrying about srcrect all the time.`
   | :sg:`Image(textureOrImage, srcrect=None) -> Image`

   .. method:: get_rect

      | :sl:`Get the rectangular area of the Image.`
      | :sg:`get_rect() -> Rect`

   .. method:: draw

      | :sl:`Copy a portion of the Image to the rendering target.`
      | :sg:`draw(srcrect=None, dstrect=None) -> None`

   .. attribute:: angle

      | :sl:`Gets and sets the angle the Image draws itself with.`
      | :sg:`angle -> float`

   .. attribute:: origin

      | :sl:`Gets and sets the origin. Origin=None means the Image will be rotated around its center.`
      | :sg:`origin -> (float, float) or None.`

   .. attribute:: flip_x

      | :sl:`Gets and sets whether the Image is flipped on the x axis.`
      | :sg:`flip_x -> bool`

   .. attribute:: flip_y

      | :sl:`Gets and sets whether the Image is flipped on the y axis.`
      | :sg:`flip_y -> bool`

   .. attribute:: color

      | :sl:`Gets and sets the Image color modifier.`
      | :sg:`color -> Color`

   .. attribute:: alpha

      | :sl:`Gets and sets the Image alpha modifier.`
      | :sg:`alpha -> float`

   .. attribute:: blend_mode

      | :sl:`Gets and sets the blend mode for the Image.`
      | :sg:`blend_mode -> int`

   .. attribute:: texture

      | :sl:`Gets and sets the Texture the Image is based on.`
      | :sg:`texture -> Texture`

   .. attribute:: srcrect

      | :sl:`Gets and sets the Rect the Image is based on.`
      | :sg:`srcrect -> Rect`

.. class:: Renderer

   | :sl:`Create a 2D rendering context for a window.`
   | :sg:`Renderer(window, index=-1, accelerated=-1, vsync=False, target_texture=False) -> Renderer`

   .. classmethod:: from_window

      | :sl:`Easy way to create a Renderer.`
      | :sg:`from_window(window) -> Renderer`

   .. attribute:: draw_blend_mode

      | :sl:`Gets and sets the blend mode used by the drawing functions.`
      | :sg:`draw_blend_mode -> int`   

   .. attribute:: draw_color

      | :sl:`Gets and sets the color used by the drawing functions.`
      | :sg:`draw_color -> Color`

   .. method:: clear

      | :sl:`Clear the current rendering target with the drawing color.`
      | :sg:`clear() -> None`

   .. method:: present

      | :sl:`Updates the screen with any new rendering since previous call.`
      | :sg:`present() -> None`	

   .. method:: get_viewport

      | :sl:`Returns the drawing area on the target.`
      | :sg:`get_viewport() -> Rect`

   .. method:: set_viewport

      | :sl:`Set the drawing area on the target. If area is None, the entire target will be used.`
      | :sg:`set_viewport(area) -> None`

   .. attribute:: logical_size

      | :sl:`Gets and sets the logical size.`
      | :sg:`logical_size -> (int width, int height)`

   .. attribute:: scale

      | :sl:`Gets and sets the scale.`
      | :sg:`scale -> (float x_scale, float y_scale)`

   .. attribute:: target

      | :sl:`Gets and sets the render target. None represents the default target (the renderer).`
      | :sg:`target -> Texture or None`

   .. method:: blit

      | :sl:`For compatibility purposes. Textures created by different Renderers cannot be shared!`
      | :sg:`blit(source, dest, area=None, special_flags=0)-> Rect`

   .. method:: draw_line

      | :sl:`Draws a line.`
      | :sg:`draw_line(p1, p2) -> None`

   .. method:: draw_point

      | :sl:`Draws a point.`
      | :sg:`draw_point(point) -> None`

   .. method:: draw_rect

      | :sl:`Draws a rectangle.`
      | :sg:`draw_rect(rect)-> None`

   .. method:: fill_rect

      | :sl:`Fills a rectangle.`
      | :sg:`fill_rect(rect)-> None`

   .. method:: to_surface

      | :sl:`Read pixels from current render target and create a pygame.Surface. WARNING: Slow operation, use sparingly.`
      | :sg:`to_surface(surface=None, area=None)-> Surface`