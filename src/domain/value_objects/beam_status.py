"""Статусы луча WCF: значения совпадают со строками радара.

Они уже лежат в сохранённых пакетах (JSON), поэтому переименование
значений ломает совместимость — менять только вместе с edge.
"""

import enum


class BeamStatus(enum.StrEnum):
    FAULT = "Fault"
    LENGTH_SIMULATED = "LengthSimulated"
    HEIGHT_SIMULATED = "HeightSimulated"
    TOO_LONG = "TooLong"
    UNKNOWN = "Unknown"
    TOO_SHORT = "TooShort"
    NOT_USED = "NotUsed"
    DISABLED = "Disabled"
    OUT_OF_PATTERN = "OutOfPattern"
    DISTANCE_NOT_UPDATING = "DistanceNotUpdating"
    WEAK_SIGNAL = "WeakSignal"
    OUT_OF_REPOSE_ANGLE = "OutOfReposeAngle"
    TOP_OUT_OF_REPOSE_ANGLE = "TopOutOfReposeAngle"
