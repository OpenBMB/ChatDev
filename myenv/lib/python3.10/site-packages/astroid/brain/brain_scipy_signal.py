# Licensed under the LGPL: https://www.gnu.org/licenses/old-licenses/lgpl-2.1.en.html
# For details: https://github.com/PyCQA/astroid/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/astroid/blob/main/CONTRIBUTORS.txt

"""Astroid hooks for scipy.signal module."""
from astroid.brain.helpers import register_module_extender
from astroid.builder import parse
from astroid.manager import AstroidManager


def scipy_signal():
    return parse(
        """
    # different functions defined in scipy.signals

    def barthann(M, sym=True):
        return numpy.ndarray([0])

    def bartlett(M, sym=True):
        return numpy.ndarray([0])

    def blackman(M, sym=True):
        return numpy.ndarray([0])

    def blackmanharris(M, sym=True):
        return numpy.ndarray([0])

    def bohman(M, sym=True):
        return numpy.ndarray([0])

    def boxcar(M, sym=True):
        return numpy.ndarray([0])

    def chebwin(M, at, sym=True):
        return numpy.ndarray([0])

    def cosine(M, sym=True):
        return numpy.ndarray([0])

    def exponential(M, center=None, tau=1.0, sym=True):
        return numpy.ndarray([0])

    def flattop(M, sym=True):
        return numpy.ndarray([0])

    def gaussian(M, std, sym=True):
        return numpy.ndarray([0])

    def general_gaussian(M, p, sig, sym=True):
        return numpy.ndarray([0])

    def hamming(M, sym=True):
        return numpy.ndarray([0])

    def hann(M, sym=True):
        return numpy.ndarray([0])

    def hanning(M, sym=True):
        return numpy.ndarray([0])

    def impulse2(system, X0=None, T=None, N=None, **kwargs):
        return numpy.ndarray([0]), numpy.ndarray([0])

    def kaiser(M, beta, sym=True):
        return numpy.ndarray([0])

    def nuttall(M, sym=True):
        return numpy.ndarray([0])

    def parzen(M, sym=True):
        return numpy.ndarray([0])

    def slepian(M, width, sym=True):
        return numpy.ndarray([0])

    def step2(system, X0=None, T=None, N=None, **kwargs):
        return numpy.ndarray([0]), numpy.ndarray([0])

    def triang(M, sym=True):
        return numpy.ndarray([0])

    def tukey(M, alpha=0.5, sym=True):
        return numpy.ndarray([0])
        """
    )


register_module_extender(AstroidManager(), "scipy.signal", scipy_signal)
