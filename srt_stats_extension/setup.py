from setuptools import setup, Extension
import os
import subprocess

# Try to find libsrt headers
def find_srt_headers():
    """Find SRT include directory"""
    possible_paths = [
        '/usr/include',
        '/usr/local/include',
        '/opt/include'
    ]
    
    for path in possible_paths:
        srt_header = os.path.join(path, 'srt', 'srt.h')
        if os.path.exists(srt_header):
            return path
    
    return '/usr/include'  # Default

# Try to find libsrt library
def find_srt_library():
    """Find SRT library directory"""
    possible_paths = [
        '/usr/lib',
        '/usr/lib/x86_64-linux-gnu',
        '/usr/local/lib',
        '/opt/lib'
    ]
    
    for path in possible_paths:
        lib_variants = [
            os.path.join(path, 'libsrt.so'),
            os.path.join(path, 'libsrt-gnutls.so'),
            os.path.join(path, 'libsrt-openssl.so')
        ]
        for lib in lib_variants:
            if os.path.exists(lib):
                return path
    
    return '/usr/lib'  # Default

include_dir = find_srt_headers()
library_dir = find_srt_library()

# Define the extension module
srt_stats_extension = Extension(
    'srt_stats',
    sources=['srt_stats.c'],
    include_dirs=[include_dir],
    library_dirs=[library_dir],
    libraries=['srt'],
    extra_compile_args=['-Wall', '-O2'],
)

setup(
    name='srt_stats',
    version='1.0.0',
    description='SRT Statistics C Extension for Python',
    author='SRT Gateway Team',
    author_email='your-email@example.com',
    ext_modules=[srt_stats_extension],
    python_requires='>=3.6',
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Programming Language :: C',
    ],
)
