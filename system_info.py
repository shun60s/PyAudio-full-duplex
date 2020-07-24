"""
PyAudio Example:

Query and print PortAudio HostAPIs, Devices, and their
support rates.
"""
"""
======================================================================

PyAudio : Python Bindings for PortAudio.

Copyright (c) 2006 Hubert Pham

Permission is hereby granted, free of charge, to any person obtaining
a copy of this software and associated documentation files (the
"Software"), to deal in the Software without restriction, including
without limitation the rights to use, copy, modify, merge, publish,
distribute, sublicense, and/or sell copies of the Software, and to
permit persons to whom the Software is furnished to do so, subject to
the following conditions:

The above copyright notice and this permission notice shall be
included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE
LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION
WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

======================================================================
"""


import pyaudio

standard_sample_rates = [8000.0, 9600.0, 11025.0, 12000.0,
                         16000.0, 22050.0, 24000.0, 32000.0,
                         44100.0, 48000.0, 88200.0, 96000.0,
                         192000.0]

p = pyaudio.PyAudio()
max_apis = p.get_host_api_count()
max_devs = p.get_device_count()

print("\nPortAudio System Info:\n======================")
print("Version: %d" % pyaudio.get_portaudio_version())
print("Version Text: %s" % pyaudio.get_portaudio_version_text())
print("Number of Host APIs: %d" % max_apis)
print("Number of Devices  : %d" % max_devs)

print("\nHost APIs:\n==========")

for i in range(max_apis):
    apiinfo = p.get_host_api_info_by_index(i)
    for k in list(apiinfo.items()):
        print("%s: %s" % k)
    print("--------------------------")

print("\nDevices:\n========")

for i in range(max_devs):
    devinfo = p.get_device_info_by_index(i)

    # print out device parameters
    for k in list(devinfo.items()):
        name, value = k

        # if host API, then get friendly name

        if name == 'hostApi':
            value = str(value) + \
                    " (%s)" % p.get_host_api_info_by_index(k[1])['name']

        # Crashing?  See http://stackoverflow.com/a/5146914
        print("\t%s: %s" % (name, value))

    # print out supported format rates

    input_supported_rates = []
    output_supported_rates = []
    full_duplex_rates = []

    for f in standard_sample_rates:

        if devinfo['maxInputChannels'] > 0:
            try:
                if p.is_format_supported(
                    f,
                    input_device = devinfo['index'],
                    input_channels = devinfo['maxInputChannels'],
                    input_format = pyaudio.paInt16):
                    input_supported_rates.append(f)
            except ValueError:
                pass

        if devinfo['maxOutputChannels'] > 0:
            try:
                if p.is_format_supported(
                    f,
                    output_device = devinfo['index'],
                    output_channels = devinfo['maxOutputChannels'],
                    output_format = pyaudio.paInt16):
                    output_supported_rates.append(f)
            except ValueError:
                pass

        if (devinfo['maxInputChannels'] > 0) and \
           (devinfo['maxOutputChannels'] > 0):
            try:
                if p.is_format_supported(
                    f,
                    input_device = devinfo['index'],
                    input_channels = devinfo['maxInputChannels'],
                    input_format = pyaudio.paInt16,
                    output_device = devinfo['index'],
                    output_channels = devinfo['maxOutputChannels'],
                    output_format = pyaudio.paInt16):
                    full_duplex_rates.append(f)
            except ValueError:
                pass

    if len(input_supported_rates):
        print("\tInput rates: %s" % input_supported_rates)
    if len(output_supported_rates):
        print("\tOutput rates: %s" % output_supported_rates)
    if len(full_duplex_rates):
        print("\tFull duplex: %s" % full_duplex_rates)

    print("\t--------------------------------")

print("\nDefault Devices:\n================")
try:
    def_index = p.get_default_input_device_info()['index']
    print("Default Input Device : %s" % def_index)
    devinfo = p.get_device_info_by_index(def_index)
    for k in list(devinfo.items()):
        name, value = k
        if name == 'hostApi':
            value = str(value) + \
                    " (%s)" % p.get_host_api_info_by_index(k[1])['name']
        print("\t%s: %s" % (name, value))
    print("\t--------------------------------")
except IOError as e:
    print("No Input devices: %s" % e[0])

try:
    def_index = p.get_default_output_device_info()['index']
    print("Default Output Device: %s" % def_index)
    devinfo = p.get_device_info_by_index(def_index)
    for k in list(devinfo.items()):
        name, value = k
        if name == 'hostApi':
            value = str(value) + \
                    " (%s)" % p.get_host_api_info_by_index(k[1])['name']
        print("\t%s: %s" % (name, value))
    print("\t--------------------------------")
except IOError as e:
    print("No Output devices: %s" % e[0])

p.terminate()
