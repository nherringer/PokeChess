"""
Build the PokeChess C++ extension via pybind11.

  pip install pybind11
  python setup.py build_ext --inplace
"""
from setuptools import setup, Extension
import pybind11

ext = Extension(
    name='pokechess_cpp',
    sources=['cpp/engine.cpp'],
    include_dirs=[pybind11.get_include()],
    language='c++',
    extra_compile_args=['-O3', '-march=native', '-std=c++17', '-fvisibility=hidden'],
)

setup(
    name='pokechess_cpp',
    ext_modules=[ext],
)
