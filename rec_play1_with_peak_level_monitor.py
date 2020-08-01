#coding:utf-8

"""
This is an experiment of PyAudio full duplex, record, filter, mix, and play simultaneously via ASIO.
And  with peak level monitor using pyqtgraph and pyQt5, every one second display changes.

Roland's old QUAD-CAPTURE has 4in/4out and can record and play simultaneously via ASIO.
Digtal audio music source is connected to COAXIAL IN (3-4) via SPDIF, FS=48KHz,
Analog signal like MIC is connected to  analog INPUT(1-2).
Via python scipy filter LPF4/HPF4, the music source mid sound is removed, and low and high sound remains.
And then, mix analog input(1-2) with the sound, and output from OUTPUT 1L/2R(1-2).
Turn MIX on QUAD-CAPTURE panel into PLAYBACK only.


music(Digital)---> COAXIAL IN(3-4) ---> Filter --|   
                                                 |   
MIC(Analog)   ---> INPUT 1L/2R(1-2) ----------> Mix --->  OUTPUT 1L/2R(1-2)


"""
"""
Copyright (c) 2020 Shun

Permission is hereby granted, free of charge, to any person obtaining a copy 
of this software and associated documentation files (the "Software"), to deal 
in the Software without restriction, including without limitation the rights 
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell 
copies of the Software, and to permit persons to whom the Software is 
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in 
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR 
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, 
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE 
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER 
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, 
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN 
THE SOFTWARE.
"""

import sys
import time
import numpy as np
import pyaudio as pa
from scipy import signal # version > 1.2.0
import pyqtgraph as pg
from pyqtgraph.Qt import QtCore, QtGui

# Check version
#  Python 3.6.4 on win32 (Windows 10)
#  numpy 1.18.4 
#  scipy 1.4.1
#  PyAudio 0.2.11 from Unofficial Windows Binaries for Python Extension Packages Includes ASIO, DS, WMME, WASAPI, WDMKS support. 
#  pyqtgraph 0.11.0
#  pyQt5  5.15.0

# global
fs48 = 48000
channel4 = 4
chunk1024 = 1024

channel2 = 2
M_peak_size = 5  # one section size per chunk1024, around 106.7mS
rbuffer_size = 300 # whole monitor duration, around 32 sec 

class FILTER4(object):
    def __init__(self,fc1=150, fc2=5000, sr=48000 ):
        # fc1 low pass filter  cut-off frequency
        # fc2 high pass filter cut-off frequency
        # sr sampling rate
        self.sr=sr
        # compute filter coefficient of LPF4 and HPF4
        self.b_l4, self.a_l4 = signal.iirfilter(4,  fc1 ,  btype='lowpass',  ftype='butter', fs=self.sr )
        self.b_h4, self.a_h4 = signal.iirfilter(4,  fc2 ,  btype='highpass', ftype='butter', fs=self.sr )
        
        # initial value of LPF4 and HPF4
        self.zi_l4_l = np.zeros( (max(len(self.a_l4), len(self.b_l4)) - 1) )
        self.zi_l4_r = np.zeros( (max(len(self.a_l4), len(self.b_l4)) - 1) )
        self.zi_h4_l = np.zeros( (max(len(self.a_h4), len(self.b_h4)) - 1) )
        self.zi_h4_r = np.zeros( (max(len(self.a_h4), len(self.b_h4)) - 1) )
        
        # average level stack buffer per M chunk
        self.m_counter=0
        self.m_peak=np.zeros((M_peak_size,channel2))
        self.stream_peak=np.zeros((rbuffer_size,channel2))
        
    def __call__(self, x_in):
        # turn to float
        in_float = np.frombuffer(x_in, dtype=np.int16).astype(np.float).reshape((chunk1024,channel4))
        
        # apply filter LPF4 HPF4 to coaxial in (3-4)
        # compute per one channel. If two channels at once, it's not work well.
        # 
        y_l4_l, self.zi_l4_l= signal.lfilter(self.b_l4, self.a_l4, in_float[:,2], zi=self.zi_l4_l)
        y_l4_r, self.zi_l4_r= signal.lfilter(self.b_l4, self.a_l4, in_float[:,3], zi=self.zi_l4_r)
        y_h4_l, self.zi_h4_l= signal.lfilter(self.b_h4, self.a_h4, in_float[:,2], zi=self.zi_h4_l)
        y_h4_r, self.zi_h4_r= signal.lfilter(self.b_h4, self.a_h4, in_float[:,3], zi=self.zi_h4_r)
        
        
        # mix input(1-2) with above filter output, and output to OUTPUT(1,2)
        in_float[:,0] += y_l4_l + y_h4_l
        in_float[:,1] += y_l4_r + y_h4_r
        # If following, sometime soud drops, due to it maybe take over time to proceed.
        #
        #in_float[:,0] += y_l4_l + y_h4_l + in_float[:,0]
        #in_float[:,1] += y_l4_r + y_h4_r + in_float[:,1]
        
        # compute average level per chunk1024
        self.m_peak[self.m_counter]= [np.amax(np.abs(in_float[:,0])),np.amax(np.abs(in_float[:,1]))]
        # stack average level per M_peak_size cycle
        self.m_counter +=1
        if self.m_counter >= M_peak_size:
            self.m_counter=0
            self.stream_peak= np.roll( self.stream_peak, -1, axis=0)  # 1 shift
            self.stream_peak[-1]= np.amax(self.m_peak,axis=0)  / float(2**15) # add as last element
        
        
        # back to int16
        return bytes(np.array(in_float, dtype=np.int16))


# instance
flt_stream= FILTER4(sr=fs48)


# define callback function, PyAudio non-blocking
def callback_rec_play(in_data, frame_count, time_info, status):
    in_data= flt_stream( in_data)
    return (in_data, pa.paContinue)


def search_device( dname=None, host_name=None):
    # get usb index number of specfied spec.
    use_device_index=None
    
    # PyAudio
    p_in = pa.PyAudio()
    for i in range(p_in.get_device_count()):
        
        devinfo= p_in.get_device_info_by_index(i)
        
        # get host api's name
        for k in list(devinfo.items()):
            name, value = k
            if name == 'hostApi':
            	host_api= p_in.get_host_api_info_by_index(k[1])['name']
        
        if dname in devinfo['name'] and host_name in host_api:
            use_device_index= i
            print ('use_device_index', use_device_index)
            print ('')
    
    # PyAudio terminate
    p_in.terminate()
    return use_device_index


class PlotWindow:
    def __init__(self):
        # init plot windows
        #pg.setConfigOption('background', 'w')
        self.win=pg.GraphicsWindow()
        self.win.setWindowTitle('peak level monitor')
        #self.win.resize(500,500)
        self.plt=self.win.addPlot()
        self.x_time= np.linspace( -1 * rbuffer_size/(fs48/chunk1024/M_peak_size), 0 , rbuffer_size)
        self.plt.setXRange( -1 * rbuffer_size/(fs48/chunk1024/M_peak_size),0)  # x-axis -5...0
        self.plt.setYRange(-100,0)  # y-axis: -100dB ...0dB
        self.plt.showGrid( True, True, 1 )
        
        self.plt.setLabel('left', '<font color=\'#' + 'FFFFFF'+'\'>'+ 'PEAK LEVEL' +'</font>', '<font color=\'#' + 'FFFFFF'+'\'>' + 'dB' +'</font>')
        self.plt.setLabel('bottom', '<font color=\'#' + 'FFFFFF'+'\'>'+ 'TIME' +'</font>', '<font color=\'#' + 'FFFFFF'+'\'>' + 'sec' +'</font>')
        self.plt.addLegend()
        
        label_list=['ch 0','ch 1']
        color_list=['r', 'b', 'g', 'c', 'm', 'y', 'k', 'w']
        self.curve=list()
        
        for i in range (len(label_list)):
            self.curve.append(self.plt.plot(pen = color_list[i], name = (label_list[i])))
        
        # update time
        self.timer=QtCore.QTimer()
        self.timer.timeout.connect(self.update)
        self.timer.start(1000)    #1000ms(=1sec) update, monitor display update time
        
    def update(self):
        #
        stream_peak= flt_stream.stream_peak.copy()
        stream_peak=np.where( stream_peak > 1.0e-6, stream_peak,1.0e-5)  # set mimimum level -100dB
        self.data1 = 20.0 * np.log10(stream_peak[:,0])
        self.data2 = 20.0 * np.log10(stream_peak[:,1])
        self.curve[0].setData(self.x_time,self.data1)   # add ch 0
        self.curve[1].setData(self.x_time,self.data2)   # add ch 1


if __name__ == "__main__":
    
    # get usb device index
    use_device_index_inout1= search_device(dname='QUAD-CAPTURE',  host_name='ASIO')
    if use_device_index_inout1 is None:
        print ('ERROR: There is not QUAD-CAPTURE ASIO.')
        sys.exit()
    
    
    # PyAudio
    p_in1 = pa.PyAudio()
    py_format_inout1 = p_in1.get_format_from_width(2)  # 16bit
    
    
    # define stream as full duplex, non-blocking
    inout_stream1 = p_in1.open(format=py_format_inout1,
                      channels=channel4,
                      rate=fs48,
                      input=True,
                      output=True,
                      frames_per_buffer=chunk1024,
                      input_device_index=use_device_index_inout1,
                      output_device_index=use_device_index_inout1,
                      stream_callback=callback_rec_play)
    
    # start stream
    inout_stream1.start_stream()
    
    # level monitor start
    plotwin=PlotWindow()
    if (sys.flags.interactive!=1) or not hasattr(QtCore, 'PYQT_VERSION'):
        QtGui.QApplication.instance().exec_()
    else:
        print('error: cannot exec QtGui QApplication.')
    
    # stream stop and close
    inout_stream1.stop_stream()
    inout_stream1.close()
    
    # PyAudio terminate
    p_in1.terminate()

