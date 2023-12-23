# mountagne

Mountagne is a disk/drive automounting service, made for Linux and runnable from a Docker container.

## Getting started

### Configuration

All the configuration is loaded from environment variables, which may either be specified on the shell, and/or an env file.
Variables from the shell have more priority. Variables keys are case-insensitive.

<!-- TODO: Statement about nomenclature of drive/device/disk/partition and normalization -->

| Name                             | Description                                                                                                                                                                                                                                                   | Default                         |
|----------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|---------------------------------|
| `ENV_FILE`                       | Path to the env file. Having an env file is not required, and execution will not fail if not found.                                                                                                                                                           | `.env`                          |
| `MOUNTPOINTS_BASE_DIR`           | Path to the directory where drives will be mounted on.                                                                                                                                                                                                        | None (required)                 |
| `WATCH_DEV_DIR`                  | Directory where to watch partitions from. A folder inside this directory is considered a partition, and its name will be the drive name.                                                                                                                      | `/dev/disk/by-label`            |
| `FILTER_ALLOW`, `FILTER_BLOCK`   | List of names of drives to allow or block from being automounted. Must be an array of strings in JSON format. Supports [Unix filename pattern matching](https://docs.python.org/3/library/fnmatch.html).                                                      | `[]` (none)                     |
| `FILESYSTEM_TYPES_OVERRIDES`     | Map of detected filesystem types (as [reported by blkid](https://www.baeldung.com/linux/find-system-type#3-using-the-blkid-command)) and the driver/type it must be passed as parameter to the mount command. Must be a map/object/dictionary in JSON format. | `{}` (none)                     |
| `AUTOMOUNT_AT_START`             | If true, automount any detected drive when Mountagne starts.                                                                                                                                                                                                  | `false`                         |
| `UNMOUNT_AT_EXIT`                | If true, unmount all the drives mounted by Mountagne when exiting.                                                                                                                                                                                            | `true`                          |
| `REMOVE_MOUNTDIRS_AFTER_UNMOUNT` | If true, directories created by Mountagne for automounting drives will be removed after the drive is unmounted.                                                                                                                                               | `true`                          |
| `BLKID_PATH`                     | Path or reference to the `blkid` binary.                                                                                                                                                                                                                      | `blkid`                         |
| Redis settings                   | Redis can optionally be used for sending mount/unmount commands.                                                                                                                                                                                              |                                 |
| `REDIS_HOST`                     | Redis server hostname/IP; if not specified, Redis will not be used.                                                                                                                                                                                           | None (optional)                 |
| `REDIS_PORT`                     | Redis server port.                                                                                                                                                                                                                                            | `6379`                          |
| `REDIS_PASSWORD`                 | Redis server password, if any.                                                                                                                                                                                                                                | None (optional)                 |
| `REDIS_DB`                       | Redis database number.                                                                                                                                                                                                                                        | `0`                             |
| `REDIS_TOPIC_COMMANDS`           | Redis key for the topic where command payloads will be read from; if not specified, will not be supported.                                                                                                                                                    | None (optional)                 |
| `REDIS_TOPIC_STATUS`             | Redis key for the topic where status updates will be sent to; if not specified, will not be supported.                                                                                                                                                        | None (optional)                 |
| `REDIS_KWARGS`                   | Additional kwargs to pass to the [Python Redis client](https://redis-py.readthedocs.io/en/stable/connections.html#generic-client). Must be a map/object/dictionary in JSON format.                                                                            | `{}` (none)                     |
| REST API settings                | An HTTP REST API can optionally be served for sending mount/unmount commands via HTTP.                                                                                                                                                                        |                                 |
| `HTTP_PORT`                      | Port for the HTTP server; if not specified, the REST API server will not be used.                                                                                                                                                                             |                                 |
| `HTTP_HOST`                      | Host (IP) where the HTTP server will listen to.                                                                                                                                                                                                               | `0.0.0.0` (bind all interfaces) |
| `HTTP_APP_NAME`                  | Name of the app (shown on auto-generated docs).                                                                                                                                                                                                               |                                 |

Mountagne will fail to initialize if the settings are not valid (i.e. a required parameter is not passed, or a value has invalid data type or format).
In this case, the error message will specify where exactly the problem is located.

#### Configuration example

Suppose we are using the following env file:

```dotenv
MOUNTPOINTS_BASE_DIR=/mnt/automount
WATCH_DEV_DIR=/dev/disk/by-label
FILTER_ALLOW='["USB*", "HDD*"]'
FILTER_BLOCK='["HDD4T1"]'
```

First of all, the `WATCH_DEV_DIR` variable makes Mountagne to watch for changes in the `/dev/disk/by-label` directory.
When a device/disk/drive/partition is plugged in, a new directory appears here, whose name is the label of the drive.
If we plug a flash drive with one partition labelled `USB64G1`, the device can be accessed from the `/dev/sdXY` path (such as `/dev/sdc1`), but also from `/dev/disk/by-label/USB64G1` (being this last the one used by our configuration, and by default).
If a device/disk/drive contains multiple partitions, each partition will have a directory in `/dev/disk/by-label`, and will be detected by Mountagne as a different partition to be mounted.

Since the device directory from the `WATCH_DEV_DIR` is named `USB64G1`, this will be used as the drive name from Mountagne.
Then, Mountagne will mount this drive in `/mnt/automount/USB64G1`.

However, remember that we are using filters (`FILTER_ALLOW` and `FILTER_BLOCK`).
This partition can be mounted because its name matches the first filter in `FILTER_ALLOW`: `USB*`, which is wildcarded to match any partition name starting by `USB`;
and the partition does not match any of the `FILTER_BLOCK` filters.

### Running from Docker example

```bash
docker run -it --rm --privileged \
-v /tmp/automount:/tmp/automount:rshared \
-v /dev:/dev:ro \
-v "$(pwd)/sample.env:/settings.env" -e ENV_FILE=/settings.env \
ghcr.io/david-lor/mountagne:latest
```

### Running locally

Mountagne is developed and tested on Python 3.10, so older Python versions may not work.
The Python requirements are:

- [requirements.txt](requirements.txt): base requirements for Mountagne.
- [requirements-redis.txt](requirements-redis.txt): additional requirements for using Redis.
- [requirements-rest.txt](requirements-rest.txt): additional requirements for serving the REST API.

It is only mandatory to install the base [requirements from requirements.txt](requirements.txt).
The additional requirements are only required (are only imported) when enabling the usage of their functionality from the Mountagne configuration.

It may be required to run Mountagne as root, so that the `mount`/`unmount` commands can be called.
Once the requirements are installed, you can run Mountagne from the repository root with: `python .`.

### Redis support

Mountagne supports receiving commands for mounting and unmounting devices, read from a Redis topic (see [Redis Pub/Sub](https://redis.io/docs/interact/pubsub/)).
Topic key is configured by the `REDIS_TOPIC_COMMANDS` setting. Payload is a JSON object with the following entries:

| Key         | Description                                                                    |
|-------------|--------------------------------------------------------------------------------|
| `operation` | Either `mount` or `unmount`.                                                   |
| `device`    | Device name to mount or unmount. Device must be present on the `WATCH_DEV_DIR` |

For example, this payload would mount a device named `USB64G1`:

```json
{
  "operation": "mount",
  "device": "USB64G1"
}
```

And this payload would unmount it:

```json
{
  "operation": "unmount",
  "device": "USB64G1"
}
```

Use the [Redis PUBLISH command](https://redis.io/commands/publish/) for sending messages:

```redis
PUBLISH mountagne/cmd '{"operation": "mount", "device": "USB64G1"}'
PUBLISH mountagne/cmd '{"operation": "unmount", "device": "USB64G1"}'
```

#### Redis updates

When any device gets mounted or unmounted, Mountagne will send a message to the `REDIS_TOPIC_STATUS` with the following format:

```json
{
  "devices": ["USB64G1", "USB64G2"]
}
```

### HTTP REST API support

Mountagne uses [FastAPI](https://fastapi.tiangolo.com/) for serving an HTTP REST API. This API supports mounting/unmounting devices via HTTP requests, as well as visualizing the currently mounting devices names.
If the HTTP server is enabled, you can see all the endpoints available in the auto-generated documentations, in: `http://{host}:{port}/docs`.

## Changelog

- v0.3
  - Add HTTP REST API server support, for mounting/unmounting and getting the currently mounted devices
  - Send updates on currently mounted devices to Redis topic
  - BREAKING: the REDIS_TOPIC_COMMANDS config param is now optional; not providing it will not listen to any commands
- v0.2
  - Support mounting/unmounting with commands from Redis
- v0.1
  - Initial release

## TODO

- Standarize nomenclatures for device/disk/drive/partition
- Add automated tests
