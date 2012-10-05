# vim: set fileencoding=utf-8 sw=4 ts=4 et :

import cffi
import fcntl
import uuid

from .fiemap import same_extents

from os import getcwd  # XXX


ffi = cffi.FFI()

ffi.cdef("""
/* ioctl.h */

#define BTRFS_IOC_TREE_SEARCH ...
#define BTRFS_IOC_INO_PATHS ...
#define BTRFS_IOC_INO_LOOKUP ...
#define BTRFS_IOC_FS_INFO ...
#define BTRFS_IOC_CLONE ...
#define BTRFS_IOC_DEFRAG ...

#define BTRFS_FSID_SIZE ...
#define BTRFS_UUID_SIZE ...

struct btrfs_ioctl_search_key {
    /* possibly the root of the search
     * though the ioctl fd seems to be used as well */
    uint64_t tree_id;

    /* keys returned will be >= min and <= max */
    uint64_t min_objectid;
    uint64_t max_objectid;

    /* keys returned will be >= min and <= max */
    uint64_t min_offset;
    uint64_t max_offset;

    /* max and min transids to search for */
    uint64_t min_transid;
    uint64_t max_transid;

    /* keys returned will be >= min and <= max */
    uint32_t min_type;
    uint32_t max_type;

    /*
     * how many items did userland ask for, and how many are we
     * returning
     */
    uint32_t nr_items;

    ...;
};

struct btrfs_ioctl_search_header {
    uint64_t transid;
    uint64_t objectid;
    uint64_t offset;
    uint32_t type;
    uint32_t len;
};

struct btrfs_ioctl_search_args {
    /* search parameters and state */
    struct btrfs_ioctl_search_key key;
    /* found items */
    char buf[];
};

struct btrfs_data_container {
    uint32_t    bytes_left; /* out -- bytes not needed to deliver output */
    uint32_t    bytes_missing;  /* out -- additional bytes needed for result */
    uint32_t    elem_cnt;   /* out */
    uint32_t    elem_missed;    /* out */
    uint64_t    val[0];     /* out */
};

struct btrfs_ioctl_ino_path_args {
    uint64_t                inum;       /* in */
    uint64_t                size;       /* in */
    /* struct btrfs_data_container  *fspath;       out */
    uint64_t                fspath;     /* out */
    ...; // reserved/padding
};

struct btrfs_ioctl_fs_info_args {
    uint64_t max_id;                /* max device id; out */
    uint64_t num_devices;           /* out */
    uint8_t fsid[16];      /* BTRFS_FSID_SIZE == 16; out */
    ...; // reserved/padding
};

struct btrfs_ioctl_ino_lookup_args {
    uint64_t treeid;
    uint64_t objectid;

    // pads to 4k; don't use this ioctl for path lookup, it's kind of broken.
    //char name[BTRFS_INO_LOOKUP_PATH_MAX];
    ...;
};


/* ctree.h */

#define BTRFS_EXTENT_DATA_KEY ...
#define BTRFS_INODE_REF_KEY ...
#define BTRFS_INODE_ITEM_KEY ...
#define BTRFS_DIR_ITEM_KEY ...
#define BTRFS_DIR_INDEX_KEY ...
#define BTRFS_ROOT_ITEM_KEY ...

#define BTRFS_FIRST_FREE_OBJECTID ...
#define BTRFS_ROOT_TREE_OBJECTID ...


struct btrfs_file_extent_item {
    /*
     * transaction id that created this extent
     */
    uint64_t generation;
    /*
     * max number of bytes to hold this extent in ram
     * when we split a compressed extent we can't know how big
     * each of the resulting pieces will be.  So, this is
     * an upper limit on the size of the extent in ram instead of
     * an exact limit.
     */
    uint64_t ram_bytes;

    /*
     * 32 bits for the various ways we might encode the data,
     * including compression and encryption.  If any of these
     * are set to something a given disk format doesn't understand
     * it is treated like an incompat flag for reading and writing,
     * but not for stat.
     */
    uint8_t compression;
    uint8_t encryption;
    uint16_t other_encoding; /* spare for later use */

    /* are we inline data or a real extent? */
    uint8_t type;

    /*
     * disk space consumed by the extent, checksum blocks are included
     * in these numbers
     */
    uint64_t disk_bytenr;
    uint64_t disk_num_bytes;
    /*
     * the logical offset in file blocks (no csums)
     * this extent record is for.  This allows a file extent to point
     * into the middle of an existing extent on disk, sharing it
     * between two snapshots (useful if some bytes in the middle of the
     * extent have changed
     */
    uint64_t offset;
    /*
     * the logical number of file blocks (no csums included)
     */
    uint64_t num_bytes;
    ...;
};

struct btrfs_timespec {
    uint64_t sec;
    uint32_t nsec;
    ...;
};

struct btrfs_inode_item {
    /* nfs style generation number */
    uint64_t generation;
    /* transid that last touched this inode */
    uint64_t transid;
    uint64_t size;
    uint64_t nbytes;
    uint64_t block_group;
    uint32_t nlink;
    uint32_t uid;
    uint32_t gid;
    uint32_t mode;
    uint64_t rdev;
    uint64_t flags;

    /* modification sequence number for NFS */
    uint64_t sequence;

    struct btrfs_timespec atime;
    struct btrfs_timespec ctime;
    struct btrfs_timespec mtime;
    struct btrfs_timespec otime;
    ...; // reserved/padding
};

struct btrfs_root_item {
// XXX CFFI and endianness: ???
    struct btrfs_inode_item inode;
    uint64_t generation;
    uint64_t root_dirid;
    uint64_t bytenr;
    uint64_t byte_limit;
    uint64_t bytes_used;
    uint64_t last_snapshot;
    uint64_t flags;
    uint32_t refs;
    struct btrfs_disk_key drop_progress;
    uint8_t drop_level;
    uint8_t level;

    /*
     * The following fields appear after subvol_uuids+subvol_times
     * were introduced.
     */

    /*
     * This generation number is used to test if the new fields are valid
     * and up to date while reading the root item. Everytime the root item
     * is written out, the "generation" field is copied into this field. If
     * anyone ever mounted the fs with an older kernel, we will have
     * mismatching generation values here and thus must invalidate the
     * new fields. See btrfs_update_root and btrfs_find_last_root for
     * details.
     * the offset of generation_v2 is also used as the start for the memset
     * when invalidating the fields.
     */
    uint64_t generation_v2;
    //uint8_t uuid[BTRFS_UUID_SIZE]; // BTRFS_UUID_SIZE == 16
    //uint8_t parent_uuid[BTRFS_UUID_SIZE];
    //uint8_t received_uuid[BTRFS_UUID_SIZE];
    uint64_t ctransid; /* updated when an inode changes */
    uint64_t otransid; /* trans when created */
    uint64_t stransid; /* trans when sent. non-zero for received subvol */
    uint64_t rtransid; /* trans when received. non-zero for received subvol */
    struct btrfs_timespec ctime;
    struct btrfs_timespec otime;
    struct btrfs_timespec stime;
    struct btrfs_timespec rtime;
    ...; // reserved and packing
};


struct btrfs_inode_ref {
    uint64_t index;
    uint16_t name_len;
    /* name goes here */
    ...;
};

struct btrfs_disk_key {
    uint64_t objectid;
    uint8_t type;
    uint64_t offset;
    ...;
};

struct btrfs_dir_item {
    struct btrfs_disk_key location;
    uint64_t transid;
    uint16_t data_len;
    uint16_t name_len;
    uint8_t type;
    ...;
};

uint64_t btrfs_stack_file_extent_generation(struct btrfs_file_extent_item *s);
uint64_t btrfs_stack_inode_generation(struct btrfs_inode_item *s);
uint64_t btrfs_stack_inode_size(struct btrfs_inode_item *s);
uint32_t btrfs_stack_inode_mode(struct btrfs_inode_item *s);
uint64_t btrfs_stack_inode_ref_name_len(struct btrfs_inode_ref *s);
uint64_t btrfs_stack_dir_name_len(struct btrfs_dir_item *s);
uint64_t btrfs_root_generation(struct btrfs_root_item *s);
""")


# Also accessible as ffi.verifier.load_library()
lib = ffi.verify('''
    #include <btrfs-progs/ioctl.h>
    #include <btrfs-progs/ctree.h>
    ''',
    include_dirs=[getcwd()])


u64_max = ffi.cast('uint64_t', -1)


def name_of_inode_ref(ref):
    namelen = lib.btrfs_stack_inode_ref_name_len(ref)
    return ffi.string(ffi.cast('char*', ref + 1), namelen)


def name_of_dir_item(item):
    namelen = lib.btrfs_stack_dir_name_len(item)
    return ffi.string(ffi.cast('char*', item + 1), namelen)


def lookup_ino_paths(volume_fd, ino):
    # This ioctl requires root
    args = ffi.new('struct btrfs_ioctl_ino_path_args*')

    # keep a reference around; args.fspath isn't a reference after the cast
    fspath = ffi.new('char[4096]')

    args.fspath = ffi.cast('uint64_t', fspath)
    args.size = 4096
    args.inum = ino

    fcntl.ioctl(volume_fd, lib.BTRFS_IOC_INO_PATHS, ffi.buffer(args))
    data_container = ffi.cast('struct btrfs_data_container *', fspath)
    if data_container.bytes_missing != 0 or data_container.elem_missed != 0:
        raise NotImplementedError  # TODO realloc fspath above

    base = ffi.cast('char*', data_container.val)
    offsets = ffi.cast('uint64_t*', data_container.val)

    for i_path in xrange(data_container.elem_cnt):
        ptr = base + offsets[i_path]
        path = ffi.string(ptr)
        yield path


def get_fsid(volume_fd):
    args = ffi.new('struct btrfs_ioctl_fs_info_args *')
    fcntl.ioctl(volume_fd, lib.BTRFS_IOC_FS_INFO, ffi.buffer(args))
    return uuid.UUID(bytes=ffi.buffer(args.fsid))


def get_root_id(volume_fd):
    args = ffi.new('struct btrfs_ioctl_ino_lookup_args *')
    # the inode of the root directory
    args.objectid = lib.BTRFS_FIRST_FREE_OBJECTID
    fcntl.ioctl(volume_fd, lib.BTRFS_IOC_INO_LOOKUP, ffi.buffer(args))
    return args.treeid


def get_root_generation(volume_fd):
    # Adapted from find_root_gen in btrfs-list.c
    # XXX I'm iffy about the search, we may not be using the most
    # recent snapshot, don't want to pick up a newer generation from
    # a different snapshot.
    treeid = get_root_id(volume_fd)
    max_found = 0

    args = ffi.new('struct btrfs_ioctl_search_args *')
    args_buffer = ffi.buffer(args)
    sk = args.key

    sk.tree_id = lib.BTRFS_ROOT_TREE_OBJECTID  # the tree of roots
    sk.min_objectid = sk.max_objectid = treeid
    sk.min_type = sk.max_type = lib.BTRFS_ROOT_ITEM_KEY
    sk.max_offset = u64_max
    sk.max_transid = u64_max

    while True:
        sk.nr_items = 4096

        fcntl.ioctl(
            volume_fd, lib.BTRFS_IOC_TREE_SEARCH, args_buffer)
        if sk.nr_items == 0:
            break

        offset = 0
        for item_id in xrange(sk.nr_items):
            sh = ffi.cast(
                'struct btrfs_ioctl_search_header *', args.buf + offset)
            offset += ffi.sizeof('struct btrfs_ioctl_search_header') + sh.len
            assert sh.objectid == treeid
            assert sh.type == lib.BTRFS_ROOT_ITEM_KEY
            item = ffi.cast(
                'struct btrfs_root_item *', sh + 1)
            max_found = max(max_found, lib.btrfs_root_generation(item))

        if sk.min_type != lib.BTRFS_ROOT_ITEM_KEY:
            break
        if sk.min_objectid != treeid:
            break
        sk.min_offset = sh.offset + 1

    assert max_found > 0
    return max_found


# clone_data and defragment also have _RANGE variants
def clone_data(dest, src, check_first):
    if check_first and same_extents(dest, src):
        return False
    fcntl.ioctl(dest, lib.BTRFS_IOC_CLONE, src)
    return True


def defragment(fd):
    # XXX Can remove compression as a side-effect
    # Also, can unshare extents.
    fcntl.ioctl(fd, lib.BTRFS_IOC_DEFRAG)


class FindError(Exception):
    pass


def find_new(volume_fd, min_generation, results_file):
    args = ffi.new('struct btrfs_ioctl_search_args *')
    args_buffer = ffi.buffer(args)
    sk = args.key

    # Not a valid objectid that I know.
    # But find-new uses that and it seems to work.
    sk.tree_id = 0

    sk.min_transid = min_generation

    sk.max_objectid = u64_max
    sk.max_offset = u64_max
    sk.max_transid = u64_max
    sk.max_type = lib.BTRFS_EXTENT_DATA_KEY

    while True:
        sk.nr_items = 4096

        try:
            fcntl.ioctl(
                volume_fd, lib.BTRFS_IOC_TREE_SEARCH, args_buffer)
        except IOError as e:
            raise FindError(e)

        if sk.nr_items == 0:
            break

        offset = 0
        for item_id in xrange(sk.nr_items):
            sh = ffi.cast(
                'struct btrfs_ioctl_search_header *', args.buf + offset)
            offset += ffi.sizeof('struct btrfs_ioctl_search_header') + sh.len

            # XXX The classic btrfs find-new looks only at extents,
            # and doesn't find empty files or directories.
            # Need to look at other types.
            if sh.type == lib.BTRFS_EXTENT_DATA_KEY:
                item = ffi.cast(
                    'struct btrfs_file_extent_item *', sh + 1)
                found_gen = lib.btrfs_stack_file_extent_generation(
                    item)
                results_file.write(
                    'item type %d ino %d len %d gen0 %d gen1 %d\n' % (
                        sh.type, sh.objectid, sh.len, sh.transid, found_gen))
                if found_gen < min_generation:
                    continue
            elif sh.type == lib.BTRFS_INODE_ITEM_KEY:
                item = ffi.cast(
                    'struct btrfs_inode_item *', sh + 1)
                found_gen = lib.btrfs_stack_inode_generation(item)
                results_file.write(
                    'item type %d ino %d len %d gen0 %d gen1 %d\n' % (
                        sh.type, sh.objectid, sh.len, sh.transid, found_gen))
                if found_gen < min_generation:
                    continue
            elif sh.type == lib.BTRFS_INODE_REF_KEY:
                ref = ffi.cast(
                    'struct btrfs_inode_ref *', sh + 1)
                name = name_of_inode_ref(ref)
                results_file.write(
                    'item type %d ino %d len %d gen0 %d name %s\n' % (
                        sh.type, sh.objectid, sh.len, sh.transid, name))
            elif (sh.type == lib.BTRFS_DIR_ITEM_KEY
                  or sh.type == lib.BTRFS_DIR_INDEX_KEY):
                item = ffi.cast(
                    'struct btrfs_dir_item *', sh + 1)
                name = name_of_dir_item(item)
                results_file.write(
                    'item type %d dir ino %d len %d'
                    ' gen0 %d gen1 %d type1 %d name %s\n' % (
                        sh.type, sh.objectid, sh.len,
                        sh.transid, item.transid, item.type, name))
            else:
                results_file.write(
                    'item type %d oid %d len %d gen0 %d\n' % (
                        sh.type, sh.objectid, sh.len, sh.transid))
        sk.min_objectid = sh.objectid
        sk.min_type = sh.type
        sk.min_offset = sh.offset

        # CFFI 0.3 raises an OverflowError if necessary, no need to assert
        #assert sk.min_offset < u64_max
        # If the OverflowError actually happens in practice,
        # we'll need to increase min_type resetting min_objectid to zero,
        # then increase min_objectid resetting min_type and min_offset to zero.
        # See
        # https://btrfs.wiki.kernel.org/index.php/Btrfs_design#Btree_Data_structures
        # and btrfs_key for the btree iteration order.
        sk.min_offset += 1

