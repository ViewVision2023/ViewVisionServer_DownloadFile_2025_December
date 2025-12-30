/*
 * SRT Statistics C Extension for Python
 * 
 * This module provides a Python interface to SRT socket statistics
 * using the native srt_bstats() function from libsrt.
 * 
 * Author: SRT Gateway Team
 * Date: November 2025
 */

#include <Python.h>
#include <srt/srt.h>

/* 
 * Get SRT statistics for a given socket
 * 
 * Args:
 *     socket_id (int): The SRT socket ID
 *     clear (int): Whether to clear statistics after reading (0 or 1)
 * 
 * Returns:
 *     dict: Dictionary with statistics, or None on error
 */
static PyObject* get_socket_stats(PyObject* self, PyObject* args) {
    SRTSOCKET socket_id;
    int clear = 0;
    SRT_TRACEBSTATS stats;
    
    // Parse arguments
    if (!PyArg_ParseTuple(args, "i|i", &socket_id, &clear)) {
        return NULL;
    }
    
    // Call srt_bstats
    int result = srt_bstats(socket_id, &stats, clear);
    
    if (result < 0) {
        // Error occurred
        PyErr_SetString(PyExc_RuntimeError, "Failed to get SRT statistics");
        return NULL;
    }
    
    // Build Python dictionary with key statistics
    return Py_BuildValue(
        "{"
        "s:d,"  // msRTT
        "s:d,"  // mbpsSendRate
        "s:d,"  // mbpsRecvRate
        "s:i,"  // pktSndLoss
        "s:i,"  // pktRcvLoss
        "s:L,"  // pktSent
        "s:L,"  // pktRecv
        "s:i,"  // pktFlightSize
        "s:i,"  // pktSndBuf
        "s:i,"  // pktRcvBuf
        "s:d,"  // mbpsBandwidth
        "s:i,"  // pktSndDrop
        "s:i,"  // pktRcvDrop
        "s:i,"  // byteAvailSndBuf
        "s:i,"  // byteAvailRcvBuf
        "s:L,"  // msTimeStamp
        "s:i"   // pktCongestionWindow
        "}",
        "msRTT", stats.msRTT,
        "mbpsSendRate", stats.mbpsSendRate,
        "mbpsRecvRate", stats.mbpsRecvRate,
        "pktSndLoss", stats.pktSndLoss,
        "pktRcvLoss", stats.pktRcvLoss,
        "pktSent", stats.pktSent,
        "pktRecv", stats.pktRecv,
        "pktFlightSize", stats.pktFlightSize,
        "pktSndBuf", stats.pktSndBuf,
        "pktRcvBuf", stats.pktRcvBuf,
        "mbpsBandwidth", stats.mbpsBandwidth,
        "pktSndDrop", stats.pktSndDrop,
        "pktRcvDrop", stats.pktRcvDrop,
        "byteAvailSndBuf", stats.byteAvailSndBuf,
        "byteAvailRcvBuf", stats.byteAvailRcvBuf,
        "msTimeStamp", stats.msTimeStamp,
        "pktCongestionWindow", stats.pktCongestionWindow
    );
}

/*
 * Check if a socket is valid and connected
 * 
 * Args:
 *     socket_id (int): The SRT socket ID
 * 
 * Returns:
 *     int: Socket state (SRTS_CONNECTED = 5)
 */
static PyObject* get_socket_state(PyObject* self, PyObject* args) {
    SRTSOCKET socket_id;
    
    if (!PyArg_ParseTuple(args, "i", &socket_id)) {
        return NULL;
    }
    
    SRT_SOCKSTATUS state = srt_getsockstate(socket_id);
    
    return PyLong_FromLong((long)state);
}

/* Module method definitions */
static PyMethodDef SrtStatsMethods[] = {
    {
        "get_stats",
        get_socket_stats,
        METH_VARARGS,
        "Get SRT socket statistics.\n\n"
        "Args:\n"
        "    socket_id (int): The SRT socket ID\n"
        "    clear (int, optional): Clear statistics after reading (default: 0)\n\n"
        "Returns:\n"
        "    dict: Dictionary containing SRT statistics\n\n"
        "Raises:\n"
        "    RuntimeError: If statistics cannot be retrieved"
    },
    {
        "get_socket_state",
        get_socket_state,
        METH_VARARGS,
        "Get SRT socket state.\n\n"
        "Args:\n"
        "    socket_id (int): The SRT socket ID\n\n"
        "Returns:\n"
        "    int: Socket state (5 = SRTS_CONNECTED)"
    },
    {NULL, NULL, 0, NULL}  /* Sentinel */
};

/* Module definition */
static struct PyModuleDef srt_stats_module = {
    PyModuleDef_HEAD_INIT,
    "srt_stats",                              /* Module name */
    "SRT statistics C extension module",      /* Module documentation */
    -1,                                       /* Module state (-1 = global) */
    SrtStatsMethods                           /* Module methods */
};

/* Module initialization */
PyMODINIT_FUNC PyInit_srt_stats(void) {
    PyObject *module;
    
    module = PyModule_Create(&srt_stats_module);
    if (module == NULL) {
        return NULL;
    }
    
    /* Add constants for socket states */
    PyModule_AddIntConstant(module, "SRTS_INIT", 1);
    PyModule_AddIntConstant(module, "SRTS_OPENED", 2);
    PyModule_AddIntConstant(module, "SRTS_LISTENING", 3);
    PyModule_AddIntConstant(module, "SRTS_CONNECTING", 4);
    PyModule_AddIntConstant(module, "SRTS_CONNECTED", 5);
    PyModule_AddIntConstant(module, "SRTS_BROKEN", 6);
    PyModule_AddIntConstant(module, "SRTS_CLOSING", 7);
    PyModule_AddIntConstant(module, "SRTS_CLOSED", 8);
    PyModule_AddIntConstant(module, "SRTS_NONEXIST", 9);
    
    return module;
}
