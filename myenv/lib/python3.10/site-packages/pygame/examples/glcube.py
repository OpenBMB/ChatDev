#!/usr/bin/env python
""" pygame.examples.glcube

Draw a cube on the screen.



Amazing.

Every frame we orbit the camera around a small amount
creating the illusion of a spinning object.

First we setup some points of a multicolored cube. Then we then go through
a semi-unoptimized loop to draw the cube points onto the screen.

OpenGL does all the hard work for us. :]


Keyboard Controls
-----------------

* ESCAPE key to quit
* f key to toggle fullscreen.

"""
import math
import ctypes

import pygame as pg

try:
    import OpenGL.GL as GL
    import OpenGL.GLU as GLU
except ImportError:
    print("pyopengl missing. The GLCUBE example requires: pyopengl numpy")
    raise SystemExit

try:
    from numpy import array, dot, eye, zeros, float32, uint32
except ImportError:
    print("numpy missing. The GLCUBE example requires: pyopengl numpy")
    raise SystemExit


# do we want to use the 'modern' OpenGL API or the old one?
# This example shows you how to do both.
USE_MODERN_GL = True

# Some simple data for a colored cube here we have the 3D point position
# and color for each corner. A list of indices describes each face, and a
# list of indices describes each edge.

CUBE_POINTS = (
    (0.5, -0.5, -0.5),
    (0.5, 0.5, -0.5),
    (-0.5, 0.5, -0.5),
    (-0.5, -0.5, -0.5),
    (0.5, -0.5, 0.5),
    (0.5, 0.5, 0.5),
    (-0.5, -0.5, 0.5),
    (-0.5, 0.5, 0.5),
)

# colors are 0-1 floating values
CUBE_COLORS = (
    (1, 0, 0),
    (1, 1, 0),
    (0, 1, 0),
    (0, 0, 0),
    (1, 0, 1),
    (1, 1, 1),
    (0, 0, 1),
    (0, 1, 1),
)

CUBE_QUAD_VERTS = (
    (0, 1, 2, 3),
    (3, 2, 7, 6),
    (6, 7, 5, 4),
    (4, 5, 1, 0),
    (1, 5, 7, 2),
    (4, 0, 3, 6),
)

CUBE_EDGES = (
    (0, 1),
    (0, 3),
    (0, 4),
    (2, 1),
    (2, 3),
    (2, 7),
    (6, 3),
    (6, 4),
    (6, 7),
    (5, 1),
    (5, 4),
    (5, 7),
)


def translate(matrix, x=0.0, y=0.0, z=0.0):
    """
    Translate (move) a matrix in the x, y and z axes.

    :param matrix: Matrix to translate.
    :param x: direction and magnitude to translate in x axis. Defaults to 0.
    :param y: direction and magnitude to translate in y axis. Defaults to 0.
    :param z: direction and magnitude to translate in z axis. Defaults to 0.
    :return: The translated matrix.
    """
    translation_matrix = array(
        [
            [1.0, 0.0, 0.0, x],
            [0.0, 1.0, 0.0, y],
            [0.0, 0.0, 1.0, z],
            [0.0, 0.0, 0.0, 1.0],
        ],
        dtype=matrix.dtype,
    ).T
    matrix[...] = dot(matrix, translation_matrix)
    return matrix


def frustum(left, right, bottom, top, znear, zfar):
    """
    Build a perspective matrix from the clipping planes, or camera 'frustrum'
    volume.

    :param left: left position of the near clipping plane.
    :param right: right position of the near clipping plane.
    :param bottom: bottom position of the near clipping plane.
    :param top: top position of the near clipping plane.
    :param znear: z depth of the near clipping plane.
    :param zfar: z depth of the far clipping plane.

    :return: A perspective matrix.
    """
    perspective_matrix = zeros((4, 4), dtype=float32)
    perspective_matrix[0, 0] = +2.0 * znear / (right - left)
    perspective_matrix[2, 0] = (right + left) / (right - left)
    perspective_matrix[1, 1] = +2.0 * znear / (top - bottom)
    perspective_matrix[3, 1] = (top + bottom) / (top - bottom)
    perspective_matrix[2, 2] = -(zfar + znear) / (zfar - znear)
    perspective_matrix[3, 2] = -2.0 * znear * zfar / (zfar - znear)
    perspective_matrix[2, 3] = -1.0
    return perspective_matrix


def perspective(fovy, aspect, znear, zfar):
    """
    Build a perspective matrix from field of view, aspect ratio and depth
    planes.

    :param fovy: the field of view angle in the y axis.
    :param aspect: aspect ratio of our view port.
    :param znear: z depth of the near clipping plane.
    :param zfar: z depth of the far clipping plane.

    :return: A perspective matrix.
    """
    h = math.tan(fovy / 360.0 * math.pi) * znear
    w = h * aspect
    return frustum(-w, w, -h, h, znear, zfar)


def rotate(matrix, angle, x, y, z):
    """
    Rotate a matrix around an axis.

    :param matrix: The matrix to rotate.
    :param angle: The angle to rotate by.
    :param x: x of axis to rotate around.
    :param y: y of axis to rotate around.
    :param z: z of axis to rotate around.

    :return: The rotated matrix
    """
    angle = math.pi * angle / 180
    c, s = math.cos(angle), math.sin(angle)
    n = math.sqrt(x * x + y * y + z * z)
    x, y, z = x / n, y / n, z / n
    cx, cy, cz = (1 - c) * x, (1 - c) * y, (1 - c) * z
    rotation_matrix = array(
        [
            [cx * x + c, cy * x - z * s, cz * x + y * s, 0],
            [cx * y + z * s, cy * y + c, cz * y - x * s, 0],
            [cx * z - y * s, cy * z + x * s, cz * z + c, 0],
            [0, 0, 0, 1],
        ],
        dtype=matrix.dtype,
    ).T
    matrix[...] = dot(matrix, rotation_matrix)
    return matrix


class Rotation:
    """
    Data class that stores rotation angles in three axes.
    """

    def __init__(self):
        self.theta = 20
        self.phi = 40
        self.psi = 25


def drawcube_old():
    """
    Draw the cube using the old open GL methods pre 3.2 core context.
    """
    allpoints = list(zip(CUBE_POINTS, CUBE_COLORS))

    GL.glBegin(GL.GL_QUADS)
    for face in CUBE_QUAD_VERTS:
        for vert in face:
            pos, color = allpoints[vert]
            GL.glColor3fv(color)
            GL.glVertex3fv(pos)
    GL.glEnd()

    GL.glColor3f(1.0, 1.0, 1.0)
    GL.glBegin(GL.GL_LINES)
    for line in CUBE_EDGES:
        for vert in line:
            pos, color = allpoints[vert]
            GL.glVertex3fv(pos)

    GL.glEnd()


def init_gl_stuff_old():
    """
    Initialise open GL, prior to core context 3.2
    """
    GL.glEnable(GL.GL_DEPTH_TEST)  # use our zbuffer

    # setup the camera
    GL.glMatrixMode(GL.GL_PROJECTION)
    GL.glLoadIdentity()
    GLU.gluPerspective(45.0, 640 / 480.0, 0.1, 100.0)  # setup lens
    GL.glTranslatef(0.0, 0.0, -3.0)  # move back
    GL.glRotatef(25, 1, 0, 0)  # orbit higher


def init_gl_modern(display_size):
    """
    Initialise open GL in the 'modern' open GL style for open GL versions
    greater than 3.1.

    :param display_size: Size of the window/viewport.
    """

    # Create shaders
    # --------------------------------------
    vertex_code = """

    #version 150
    uniform mat4   model;
    uniform mat4   view;
    uniform mat4   projection;

    uniform vec4   colour_mul;
    uniform vec4   colour_add;

    in vec4 vertex_colour;         // vertex colour in
    in vec3 vertex_position;

    out vec4   vertex_color_out;            // vertex colour out
    void main()
    {
        vertex_color_out = (colour_mul * vertex_colour) + colour_add;
        gl_Position = projection * view * model * vec4(vertex_position, 1.0);
    }

    """

    fragment_code = """
    #version 150
    in vec4 vertex_color_out;  // vertex colour from vertex shader
    out vec4 fragColor;
    void main()
    {
        fragColor = vertex_color_out;
    }
    """

    program = GL.glCreateProgram()
    vertex = GL.glCreateShader(GL.GL_VERTEX_SHADER)
    fragment = GL.glCreateShader(GL.GL_FRAGMENT_SHADER)
    GL.glShaderSource(vertex, vertex_code)
    GL.glCompileShader(vertex)

    # this logs issues the shader compiler finds.
    log = GL.glGetShaderInfoLog(vertex)
    if isinstance(log, bytes):
        log = log.decode()
    for line in log.split("\n"):
        print(line)

    GL.glAttachShader(program, vertex)
    GL.glShaderSource(fragment, fragment_code)
    GL.glCompileShader(fragment)

    # this logs issues the shader compiler finds.
    log = GL.glGetShaderInfoLog(fragment)
    if isinstance(log, bytes):
        log = log.decode()
    for line in log.split("\n"):
        print(line)

    GL.glAttachShader(program, fragment)
    GL.glValidateProgram(program)
    GL.glLinkProgram(program)

    GL.glDetachShader(program, vertex)
    GL.glDetachShader(program, fragment)
    GL.glUseProgram(program)

    # Create vertex buffers and shader constants
    # ------------------------------------------

    # Cube Data
    vertices = zeros(
        8, [("vertex_position", float32, 3), ("vertex_colour", float32, 4)]
    )

    vertices["vertex_position"] = [
        [1, 1, 1],
        [-1, 1, 1],
        [-1, -1, 1],
        [1, -1, 1],
        [1, -1, -1],
        [1, 1, -1],
        [-1, 1, -1],
        [-1, -1, -1],
    ]

    vertices["vertex_colour"] = [
        [0, 1, 1, 1],
        [0, 0, 1, 1],
        [0, 0, 0, 1],
        [0, 1, 0, 1],
        [1, 1, 0, 1],
        [1, 1, 1, 1],
        [1, 0, 1, 1],
        [1, 0, 0, 1],
    ]

    filled_cube_indices = array(
        [
            0,
            1,
            2,
            0,
            2,
            3,
            0,
            3,
            4,
            0,
            4,
            5,
            0,
            5,
            6,
            0,
            6,
            1,
            1,
            6,
            7,
            1,
            7,
            2,
            7,
            4,
            3,
            7,
            3,
            2,
            4,
            7,
            6,
            4,
            6,
            5,
        ],
        dtype=uint32,
    )

    outline_cube_indices = array(
        [0, 1, 1, 2, 2, 3, 3, 0, 4, 7, 7, 6, 6, 5, 5, 4, 0, 5, 1, 6, 2, 7, 3, 4],
        dtype=uint32,
    )

    shader_data = {"buffer": {}, "constants": {}}

    GL.glBindVertexArray(GL.glGenVertexArrays(1))  # Have to do this first

    shader_data["buffer"]["vertices"] = GL.glGenBuffers(1)
    GL.glBindBuffer(GL.GL_ARRAY_BUFFER, shader_data["buffer"]["vertices"])
    GL.glBufferData(GL.GL_ARRAY_BUFFER, vertices.nbytes, vertices, GL.GL_DYNAMIC_DRAW)

    stride = vertices.strides[0]
    offset = ctypes.c_void_p(0)

    loc = GL.glGetAttribLocation(program, "vertex_position")
    GL.glEnableVertexAttribArray(loc)
    GL.glVertexAttribPointer(loc, 3, GL.GL_FLOAT, False, stride, offset)

    offset = ctypes.c_void_p(vertices.dtype["vertex_position"].itemsize)

    loc = GL.glGetAttribLocation(program, "vertex_colour")
    GL.glEnableVertexAttribArray(loc)
    GL.glVertexAttribPointer(loc, 4, GL.GL_FLOAT, False, stride, offset)

    shader_data["buffer"]["filled"] = GL.glGenBuffers(1)
    GL.glBindBuffer(GL.GL_ELEMENT_ARRAY_BUFFER, shader_data["buffer"]["filled"])
    GL.glBufferData(
        GL.GL_ELEMENT_ARRAY_BUFFER,
        filled_cube_indices.nbytes,
        filled_cube_indices,
        GL.GL_STATIC_DRAW,
    )

    shader_data["buffer"]["outline"] = GL.glGenBuffers(1)
    GL.glBindBuffer(GL.GL_ELEMENT_ARRAY_BUFFER, shader_data["buffer"]["outline"])
    GL.glBufferData(
        GL.GL_ELEMENT_ARRAY_BUFFER,
        outline_cube_indices.nbytes,
        outline_cube_indices,
        GL.GL_STATIC_DRAW,
    )

    shader_data["constants"]["model"] = GL.glGetUniformLocation(program, "model")
    GL.glUniformMatrix4fv(shader_data["constants"]["model"], 1, False, eye(4))

    shader_data["constants"]["view"] = GL.glGetUniformLocation(program, "view")
    view = translate(eye(4), z=-6)
    GL.glUniformMatrix4fv(shader_data["constants"]["view"], 1, False, view)

    shader_data["constants"]["projection"] = GL.glGetUniformLocation(
        program, "projection"
    )
    GL.glUniformMatrix4fv(shader_data["constants"]["projection"], 1, False, eye(4))

    # This colour is multiplied with the base vertex colour in producing
    # the final output
    shader_data["constants"]["colour_mul"] = GL.glGetUniformLocation(
        program, "colour_mul"
    )
    GL.glUniform4f(shader_data["constants"]["colour_mul"], 1, 1, 1, 1)

    # This colour is added on to the base vertex colour in producing
    # the final output
    shader_data["constants"]["colour_add"] = GL.glGetUniformLocation(
        program, "colour_add"
    )
    GL.glUniform4f(shader_data["constants"]["colour_add"], 0, 0, 0, 0)

    # Set GL drawing data
    # -------------------
    GL.glClearColor(0, 0, 0, 0)
    GL.glPolygonOffset(1, 1)
    GL.glEnable(GL.GL_LINE_SMOOTH)
    GL.glBlendFunc(GL.GL_SRC_ALPHA, GL.GL_ONE_MINUS_SRC_ALPHA)
    GL.glDepthFunc(GL.GL_LESS)
    GL.glHint(GL.GL_LINE_SMOOTH_HINT, GL.GL_NICEST)
    GL.glLineWidth(1.0)

    projection = perspective(45.0, display_size[0] / float(display_size[1]), 2.0, 100.0)
    GL.glUniformMatrix4fv(shader_data["constants"]["projection"], 1, False, projection)

    return shader_data, filled_cube_indices, outline_cube_indices


def draw_cube_modern(shader_data, filled_cube_indices, outline_cube_indices, rotation):
    """
    Draw a cube in the 'modern' Open GL style, for post 3.1 versions of
    open GL.

    :param shader_data: compile vertex & pixel shader data for drawing a cube.
    :param filled_cube_indices: the indices to draw the 'filled' cube.
    :param outline_cube_indices: the indices to draw the 'outline' cube.
    :param rotation: the current rotations to apply.
    """

    GL.glClear(GL.GL_COLOR_BUFFER_BIT | GL.GL_DEPTH_BUFFER_BIT)

    # Filled cube
    GL.glDisable(GL.GL_BLEND)
    GL.glEnable(GL.GL_DEPTH_TEST)
    GL.glEnable(GL.GL_POLYGON_OFFSET_FILL)
    GL.glUniform4f(shader_data["constants"]["colour_mul"], 1, 1, 1, 1)
    GL.glUniform4f(shader_data["constants"]["colour_add"], 0, 0, 0, 0.0)
    GL.glBindBuffer(GL.GL_ELEMENT_ARRAY_BUFFER, shader_data["buffer"]["filled"])
    GL.glDrawElements(
        GL.GL_TRIANGLES, len(filled_cube_indices), GL.GL_UNSIGNED_INT, None
    )

    # Outlined cube
    GL.glDisable(GL.GL_POLYGON_OFFSET_FILL)
    GL.glEnable(GL.GL_BLEND)
    GL.glUniform4f(shader_data["constants"]["colour_mul"], 0, 0, 0, 0.0)
    GL.glUniform4f(shader_data["constants"]["colour_add"], 1, 1, 1, 1.0)
    GL.glBindBuffer(GL.GL_ELEMENT_ARRAY_BUFFER, shader_data["buffer"]["outline"])
    GL.glDrawElements(GL.GL_LINES, len(outline_cube_indices), GL.GL_UNSIGNED_INT, None)

    # Rotate cube
    # rotation.theta += 1.0  # degrees
    rotation.phi += 1.0  # degrees
    # rotation.psi += 1.0  # degrees
    model = eye(4, dtype=float32)
    # rotate(model, rotation.theta, 0, 0, 1)
    rotate(model, rotation.phi, 0, 1, 0)
    rotate(model, rotation.psi, 1, 0, 0)
    GL.glUniformMatrix4fv(shader_data["constants"]["model"], 1, False, model)


def main():
    """run the demo"""

    # initialize pygame and setup an opengl display
    pg.init()

    gl_version = (3, 0)  # GL Version number (Major, Minor)
    if USE_MODERN_GL:
        gl_version = (3, 2)  # GL Version number (Major, Minor)

        # By setting these attributes we can choose which Open GL Profile
        # to use, profiles greater than 3.2 use a different rendering path
        pg.display.gl_set_attribute(pg.GL_CONTEXT_MAJOR_VERSION, gl_version[0])
        pg.display.gl_set_attribute(pg.GL_CONTEXT_MINOR_VERSION, gl_version[1])
        pg.display.gl_set_attribute(
            pg.GL_CONTEXT_PROFILE_MASK, pg.GL_CONTEXT_PROFILE_CORE
        )

    fullscreen = False  # start in windowed mode

    display_size = (640, 480)
    pg.display.set_mode(display_size, pg.OPENGL | pg.DOUBLEBUF | pg.RESIZABLE)

    if USE_MODERN_GL:
        gpu, f_indices, o_indices = init_gl_modern(display_size)
        rotation = Rotation()
    else:
        init_gl_stuff_old()

    going = True
    while going:
        # check for quit'n events
        events = pg.event.get()
        for event in events:
            if event.type == pg.QUIT or (
                event.type == pg.KEYDOWN and event.key == pg.K_ESCAPE
            ):
                going = False

            elif event.type == pg.KEYDOWN and event.key == pg.K_f:
                if not fullscreen:
                    print("Changing to FULLSCREEN")
                    pg.display.set_mode(
                        (640, 480), pg.OPENGL | pg.DOUBLEBUF | pg.FULLSCREEN
                    )
                else:
                    print("Changing to windowed mode")
                    pg.display.set_mode((640, 480), pg.OPENGL | pg.DOUBLEBUF)
                fullscreen = not fullscreen
                if gl_version[0] >= 4 or (gl_version[0] == 3 and gl_version[1] >= 2):
                    gpu, f_indices, o_indices = init_gl_modern(display_size)
                    rotation = Rotation()
                else:
                    init_gl_stuff_old()

        if USE_MODERN_GL:
            draw_cube_modern(gpu, f_indices, o_indices, rotation)
        else:
            # clear screen and move camera
            GL.glClear(GL.GL_COLOR_BUFFER_BIT | GL.GL_DEPTH_BUFFER_BIT)
            # orbit camera around by 1 degree
            GL.glRotatef(1, 0, 1, 0)
            drawcube_old()

        pg.display.flip()
        pg.time.wait(10)

    pg.quit()


if __name__ == "__main__":
    main()
