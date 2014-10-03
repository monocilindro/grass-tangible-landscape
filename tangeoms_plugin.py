# -*- coding: utf-8 -*-
"""
Created on Wed Nov 20 14:44:32 2013

@author: anna
"""
import threading
import wx
import subprocess
import os
import numpy as np
from tempfile import gettempdir

import wx.lib.newevent
from import_xyz import import_scan
from subsurface import compute_crosssection

updateGUIEvt, EVT_UPDATE_GUI = wx.lib.newevent.NewCommandEvent()


class TangeomsPlugin(wx.Dialog):
    def __init__(self, giface, parent):
        wx.Dialog.__init__(self, parent)
        self.giface=giface
        self.parent=parent
        mainSizer = wx.BoxSizer(wx.VERTICAL)
        mainSizer.Add(wx.StaticText(self, label="Press start to start"),
                      proportion=0, flag=wx.EXPAND | wx.ALL, border=5)
        btnCalibrate = wx.Button(self, label="Calibrate")
        btnStart = wx.Button(self, label="Start")
        btnStop = wx.Button(self, label="Stop")
        self.btnPause = wx.Button(self, label="Pause")
        btnClose = wx.Button(self, label="Close")

        btnStart.Bind(wx.EVT_BUTTON, lambda evt: self.Start())
        btnStop.Bind(wx.EVT_BUTTON, lambda evt: self.Stop())
        btnClose.Bind(wx.EVT_BUTTON, self.OnClose)
        btnCalibrate.Bind(wx.EVT_BUTTON, self.Calibrate)
        self.btnPause.Bind(wx.EVT_BUTTON, lambda evt: self.Pause())
        self.Bind(wx.EVT_CLOSE, self.OnClose)
        self.Bind(EVT_UPDATE_GUI, self.OnUpdate)

        btnSizer = wx.BoxSizer(wx.HORIZONTAL)
        btnSizer.Add(btnCalibrate, proportion=0, flag=wx.ALL, border=2)
        btnSizer.Add(btnStart, proportion=0, flag=wx.ALL, border=2)
        btnSizer.Add(btnStop, proportion=0, flag=wx.ALL, border=2)
        btnSizer.Add(self.btnPause, proportion=0, flag=wx.ALL, border=2)
        btnSizer.Add(btnClose, proportion=0, flag=wx.ALL, border=2)
        mainSizer.Add(btnSizer, proportion=0, flag=wx.EXPAND | wx.ALL, border=5)

        self.SetSizer(mainSizer)
        mainSizer.Fit(self)

    def OnClose(self, event):
        self.Stop()
        self.Destroy()

    def Start(self):
        raise NotImplementedError

    def Stop(self):
        raise NotImplementedError

    def OnUpdate(self, event):
        self.giface.updateMap()

    def Calibrate(self, event):
        from prepare_calibration import write_matrix
        print 'REMOVE EVERYTHING FROM TABLE'
        matrix_file_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'calib_matrix.npy')
        write_matrix(matrix_path=matrix_file_path, min_z=0.5, max_z=0.8)


class TangeomsImportPlugin(TangeomsPlugin):
    def __init__(self, giface, guiparent,  elev_real, scan, diff, scanFile, minZ, maxZ):
        TangeomsPlugin.__init__(self, giface, guiparent)
        self.elevation=elev_real
        self.diff = diff
        self.output = scan
        self.tmp_file = scanFile
        self.minZ = minZ
        self.maxZ = maxZ
        calib = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'calib_matrix.npy')
        if os.path.exists(calib):
            self.calib_matrix = np.load(calib)
        else:
            self.calib_matrix = None
            giface.WriteWarning("WARNING: No calibration file exists")
        self.threadI = None
        self.stopEvt = None


    def CreateThread(self):
        self.stopEvt = threading.Event()
        self.threadI = threading.Thread(target=runImport, args=[self, self.tmp_file, self.elevation,
                                                                self.output, self.diff, self.calib_matrix, self.stopEvt])

    def Start(self):
        if not self.threadI or not self.threadI.isAlive():
            kinectApp = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'kinect', 'scan_cont', 'KinectFusionExplorer-D2D.exe')
            subprocess.Popen([kinectApp, self.tmp_file, '20'] )
            self.CreateThread()
            self.threadI.start()

    def Stop(self):
        subprocess.call(['taskkill', '/f', '/im', 'KinectFusionExplorer-D2D.exe'])
        if self.threadI and self.threadI.isAlive():
            self.stopEvt.set()

    def Pause(self):
        if self.threadI and self.threadI.isAlive():
            self.stopEvt.set()
            self.btnPause.SetLabel("Resume")
        else:
            self.CreateThread()
            self.threadI.start()
            self.btnPause.SetLabel("Pause")


def runImport(guiParent, fileName, elevation, scan, diff, calib_matrix, stopEvent):
    lockFilePath = fileName + 'lock'
    if os.path.exists(fileName):
        lastTime = os.path.getmtime(fileName)
    else:
        lastTime = None
    currTime = 0
    os.environ['GRASS_MESSAGE_FORMAT'] = 'standard'

    while not stopEvent.is_set():
        if not os.path.exists(lockFilePath) and os.path.exists(fileName):
            currTime = os.path.getmtime(fileName)
            if currTime == lastTime:
                continue
            lastTime = currTime
            print 'RUNNING IMPORT'
            import_scan(input_file=fileName, real_elev=elevation, output_elev=scan,
                               mm_resolution=0.001, calib_matrix=calib_matrix, table_mm=8, zexag=3, interpolate=True)
#            compute_crosssection(real_elev='extent', output_elev=scan, output_diff='diff', output_cross='cross', voxel='interp_2002_08_25',
#                                 scan_file_path=fileName, calib_matrix=calib_matrix, zexag=0.7, table_mm=2, edge_mm=[10, 10, 0, 0], mm_resolution=0.001)
            print 'IMPORT END'
            evt = updateGUIEvt(guiParent.GetId())
            wx.PostEvent(guiParent, evt)


def run(giface, guiparent):
    dlg = TangeomsImportPlugin(giface, guiparent, elev_real='elevation', scan='scan', diff='diff',
                scanFile=os.path.join(os.path.realpath(gettempdir()), 'kinect_scan.txt'), minZ=0.4, maxZ=0.85)
    dlg.CenterOnParent()
    dlg.Show()


if __name__ == '__main__':
    run(None, None)
