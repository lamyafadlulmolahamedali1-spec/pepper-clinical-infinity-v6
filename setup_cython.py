"""
╔══════════════════════════════════════════════════════════════════════╗
║  PEPPER CLINICAL INFINITY V6 — Cython Compilation                  ║
║  © 2026 Lamya Fadlulmola Hamed Ali — All Rights Reserved           ║
║                                                                      ║
║  Converts pepper_v6_full.py → compiled .so binary (unreadable)     ║
║  Run:  python setup_cython.py build_ext --inplace                   ║
╚══════════════════════════════════════════════════════════════════════╝
"""
from setuptools import setup
from Cython.Build import cythonize
from Cython.Compiler import Options

# Maximum protection settings
Options.annotate          = False   # no HTML annotation output
Options.embed_pos_in_docstring = False
Options.generate_cleanup_code  = True

setup(
    name="PepperClinicalV6",
    version="6.0.0",
    author="Lamya Fadlulmola Hamed Ali",
    description="Pepper Clinical Infinity V6 — ASD Therapy Platform",
    ext_modules=cythonize(
        ["pepper_v6_full.py"],
        compiler_directives={
            "language_level": "3",
            "boundscheck":    False,
            "wraparound":     False,
            "cdivision":      True,
            "nonecheck":      False,
            "optimize.use_switch": True,
            "optimize.unpack_method_calls": True,
            "embedsignature": False,   # hide signatures
            "emit_code_comments": False,  # no comments in C output
        },
        annotate=False,
    ),
    zip_safe=False,
)
