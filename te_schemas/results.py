import base64
import binascii
import dataclasses
import enum
import typing
from dataclasses import field

import marshmallow_dataclass
from marshmallow import validate
from marshmallow_dataclass.typing import Url

from .path import Path


class ResultType(enum.Enum):
    CLOUD_RESULTS = "CloudResults"
    RASTER_RESULTS = "RasterResults"
    LOCAL_RESULTS = "LocalResults"
    TIME_SERIES_TABLE = "TimeSeriesTable"
    JSON_RESULTS = "JsonResults"
    EMPTY_RESULTS = "EmptyResults"


class DataType(enum.Enum):
    BYTE = "Byte"
    UINT16 = "UInt16"
    INT16 = "Int16"
    UINT32 = "UInt32"
    INT32 = "Int32"
    FLOAT32 = "Float32"
    FLOAT64 = "Float64"


class RasterType(enum.Enum):
    TILED_RASTER = "Tiled raster"
    ONE_FILE_RASTER = "One file raster"


class RasterFileType(enum.Enum):
    GEOTIFF = "GeoTiff"
    COG = "COG"


class EtagType(enum.Enum):
    AWS_MD5 = "AWS MD5 Etag"
    AWS_MULTIPART = "AWS Multipart Etag"
    GCS_CRC32C = "GCS CRC32C Etag"
    GCS_MD5 = "GCS MD5 Etag"


@marshmallow_dataclass.dataclass
class Etag:
    hash: str
    type: EtagType = dataclasses.field(metadata={"by_value": True})

    #TODO: Fix below as doesn't work on an s3 file uploaded with multipart
    @property
    def decoded_hash(self):
        return binascii.hexlify(base64.b64decode(self.md5_hash)).decode()


@marshmallow_dataclass.dataclass
class URI:
    uri: typing.Union[Url, Path]
    type: str = field(
        metadata={'validate': validate.OneOf(["local", "cloud"])})
    etag: typing.Optional[Etag] = None


@marshmallow_dataclass.dataclass
class Band:
    name: str
    metadata: dict
    no_data_value: typing.Union[int, float] = -32768
    activated: typing.Optional[bool] = dataclasses.field(default=True)
    add_to_map: typing.Optional[bool] = dataclasses.field(default=True)


@marshmallow_dataclass.dataclass
class TiledRaster:
    tile_uris: typing.List[URI]
    bands: typing.List[Band]
    datatype: DataType = dataclasses.field(metadata={"by_value": True})
    filetype: RasterFileType = dataclasses.field(metadata={"by_value": True})
    uri: typing.Optional[
        URI] = None  # should point to a single VRT file linking the tiles
    type: RasterType = dataclasses.field(default=RasterType.TILED_RASTER,
                                         metadata={"by_value": True})


@marshmallow_dataclass.dataclass
class Raster:
    uri: URI
    bands: typing.List[Band]
    datatype: DataType = dataclasses.field(metadata={"by_value": True})
    filetype: RasterFileType = dataclasses.field(metadata={"by_value": True})
    type: RasterType = dataclasses.field(default=RasterType.ONE_FILE_RASTER,
                                         metadata={"by_value": True})


@marshmallow_dataclass.dataclass
class RasterResults:
    name: str
    rasters: typing.Dict[str, typing.Union[Raster, TiledRaster]]
    uri: typing.Optional[
        URI] = None  # should point to a single VRT or tif linking all rasters
    data: typing.Optional[dict] = dataclasses.field(default_factory=dict)
    type: ResultType = dataclasses.field(default=ResultType.RASTER_RESULTS,
                                         metadata={"by_value": True})

    def has_tiled_raster(self):
        for key, raster in self.rasters.items():
            if raster.type == RasterType.TILED_RASTER:
                return True

        return False

    def get_main_uris(self):
        return [raster.uri for raster in self.rasters.values()]

    def get_all_uris(self):
        if self.uri:
            uris = [self.uri]  # main vrt

        for raster in self.rasters.values():
            if raster.uri:
                uris.append(raster.uri)  # tif or main vrt (for TiledRaster)

            if raster.type == ResultType.RASTER_RESULTS:
                if raster.tile_uris:
                    uris.extend(raster.tile_uris)  # tif (for TiledRaster)

        return uris

    def get_bands(self):
        return [b for raster in self.rasters.values() for b in raster.bands]

    def get_band_uris(self):
        return [
            raster.uri for raster in self.rasters.values()
            for b in raster.bands
        ]


@marshmallow_dataclass.dataclass
class EmptyResults:
    class Meta:
        unknown = 'EXCLUDE'

    name: typing.Optional[str] = None
    data_path: typing.Optional[Path] = None
    type: ResultType = dataclasses.field(default=ResultType.EMPTY_RESULTS,
                                         metadata={"by_value": True})


@marshmallow_dataclass.dataclass
class CloudResults:
    class Meta:
        unknown = 'EXCLUDE'

    name: str
    bands: typing.List[Band]
    urls: typing.List[Url]
    data_path: typing.Optional[Path] = dataclasses.field(default=None)
    other_paths: typing.Optional[typing.List[Path]] = dataclasses.field(
        default_factory=list)
    data: typing.Optional[dict] = dataclasses.field(default_factory=dict)
    type: ResultType = dataclasses.field(default=ResultType.CLOUD_RESULTS,
                                         metadata={"by_value": True})


@marshmallow_dataclass.dataclass
class LocalResults:
    class Meta:
        unknown = 'EXCLUDE'

    name: str
    bands: typing.List[Band]
    data_path: typing.Optional[Path] = dataclasses.field(default=None)
    other_paths: typing.List[Path] = dataclasses.field(default_factory=list)
    data: typing.Optional[dict] = dataclasses.field(default_factory=dict)
    type: ResultType = dataclasses.field(default=ResultType.LOCAL_RESULTS,
                                         metadata={"by_value": True})


@marshmallow_dataclass.dataclass
class JsonResults:
    class Meta:
        unknown = 'EXCLUDE'

    name: str
    data: dict

    type: ResultType = dataclasses.field(default=ResultType.JSON_RESULTS,
                                         metadata={"by_value": True})


@marshmallow_dataclass.dataclass
class TimeSeriesTableResult:
    class Meta:
        unknown = 'EXCLUDE'

    name: str
    table: typing.List[dict]
    type: ResultType = dataclasses.field(default=ResultType.TIME_SERIES_TABLE,
                                         metadata={"by_value": True})
