# mountagne

Mountagne is a disk/drive automounting service, made for Linux and runnable from a Docker container.

## Getting started

### Configuration

All the configuration is loaded from environment variables, which may either be specified on the shell, and/or an env file.
Variables from the shell have more priority. Variables keys are case-insensitive.

<!-- TODO: Statement about nomenclature of drive/device/disk/partition and normalization -->

| Name                             | Description                                                                                                                                                                                                                                                   | Default              |
|----------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|----------------------|
| `ENV_FILE`                       | Path to the env file. Having an env file is not required, and execution will not fail if not found.                                                                                                                                                           | `.env`               |
| `MOUNTPOINTS_BASE_DIR`           | Path to the directory where drives will be mounted on.                                                                                                                                                                                                        | None (required)      |
| `WATCH_DEV_DIR`                  | Directory where to watch partitions from. A folder inside this directory is considered a partition, and its name will be the drive name.                                                                                                                      | `/dev/disk/by-label` |
| `FILTER_ALLOW`, `FILTER_BLOCK`   | List of names of drives to allow or block from being automounted. Must be an array of strings in JSON format. Supports [Unix filename pattern matching](https://docs.python.org/3/library/fnmatch.html).                                                      | `[]` (none)          |
| `FILESYSTEM_TYPES_OVERRIDES`     | Map of detected filesystem types (as [reported by blkid](https://www.baeldung.com/linux/find-system-type#3-using-the-blkid-command)) and the driver/type it must be passed as parameter to the mount command. Must be a map/object/dictionary in JSON format. | `{}` (none)          |
| `AUTOMOUNT_AT_START`             | If true, automount any detected drive when Mountagne starts.                                                                                                                                                                                                  | `false`              |
| `UNMOUNT_AT_EXIT`                | If true, unmount all the drives mounted by Mountagne when exiting.                                                                                                                                                                                            | `true`               |
| `REMOVE_MOUNTDIRS_AFTER_UNMOUNT` | If true, directories created by Mountagne for automounting drives will be removed after the drive is unmounted.                                                                                                                                               | `true`               |
| `BLKID_PATH`                     | Path or reference to the `blkid` binary.                                                                                                                                                                                                                      | `blkid`              |

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
local/mountagne
```

## TODO

- Support mounting/unmounting on-demand (from an external source: MQTT, Redis, files?)
- Add automated tests
