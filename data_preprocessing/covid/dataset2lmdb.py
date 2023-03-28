import os
import os.path as osp
from PIL import Image
import six
import lmdb
import pickle
import numpy as np

import torch.utils.data as data
from torch.utils.data import DataLoader,Subset
from torchvision.datasets import ImageFolder

import torch

from sklearn.model_selection import train_test_split

def train_val_dataset(dataset, val_split=0.25):
    train_idx, val_idx = train_test_split(list(range(len(dataset))), test_size=val_split)
    datasets = [Subset(dataset, train_idx), Subset(dataset, val_idx)]
    # datasets['train'] = 
    # datasets['val'] =
    return datasets

# from data_loader import get_dataloader_?test_cinic10


def loads_data(buf):
    """
    Args:
        buf: the output of `dumps`.
    """
    return pickle.loads(buf)


class ImageFolderLMDB(data.Dataset):
    def __init__(self, db_path, transform=None, target_transform=None):
        self.db_path = db_path
        self.env = lmdb.open(db_path, subdir=osp.isdir(db_path),
                             readonly=True, lock=False,
                             readahead=False, meminit=False)
        with self.env.begin(write=False) as txn:
            self.length = loads_data(txn.get(b'__len__'))
            self.keys = loads_data(txn.get(b'__keys__'))

        self.transform = transform
        self.target_transform = target_transform

    def __getitem__(self, index):
        env = self.env
        with env.begin(write=False) as txn:
            byteflow = txn.get(self.keys[index])

        unpacked = loads_data(byteflow)

        # load img
        imgbuf = unpacked[0]
        buf = six.BytesIO()
        buf.write(imgbuf)
        buf.seek(0)
        img = Image.open(buf).convert('RGB')

        # load label
        target = unpacked[1]

        if self.transform is not None:
            img = self.transform(img)

        im2arr = np.array(img)

        if self.target_transform is not None:
            target = self.target_transform(target)

        # return img, target
        return im2arr, target

    def __len__(self):
        return self.length

    def __repr__(self):
        return self.__class__.__name__ + ' (' + self.db_path + ')'


def raw_reader(path):
    with open(path, 'rb') as f:
        bin_data = f.read()
    return bin_data


def dumps_data(obj):
    """
    Serialize an object.
    Returns:
        Implementation-dependent bytes-like object
    """
    return pickle.dumps(obj)


def folder2lmdb(dpath,name, write_frequency=5000):
    directory = osp.expanduser(dpath)
    print("Loading dataset from %s" % directory)
    dataset = ImageFolder(directory, loader=raw_reader)
    print(dataset.classes)
    datasets = train_val_dataset(dataset)

    if name == "train":
        dataset_inner = datasets[0]
    else:
        dataset_inner = datasets[1]


    data_loader = DataLoader(dataset_inner, num_workers=16, collate_fn=lambda x: x)

    # data_loaders = get_dataloader_test_cinic10(dpath, 1, 1,transform = False)




    lmdb_path = osp.join(dpath, "%s.lmdb" % name)
    isdir = os.path.isdir(lmdb_path)

    print("Generate LMDB to %s" % lmdb_path)
    db = lmdb.open(lmdb_path, subdir=isdir,
                   map_size=1099511627776 * 2, readonly=False,
                   meminit=False, map_async=True)

    txn = db.begin(write=True)
    labels = []
    for idx, data in enumerate(data_loader):
        image, label = data[0]
        labels.append(label)

        txn.put(u'{}'.format(idx).encode('ascii'), dumps_data((image, label)))
        if idx % write_frequency == 0:
            print("[%d/%d]" % (idx, len(data_loader)))
            txn.commit()
            txn = db.begin(write=True)

    # finish iterating through dataset
    txn.commit()
    keys = [u'{}'.format(k).encode('ascii') for k in range(idx + 1)]
    labels = np.array(labels)
    with db.begin(write=True) as txn:
        txn.put(b'__keys__', dumps_data(zip(keys,labels)))
        txn.put(b'__len__', dumps_data(len(keys)))
        # txn.put(b'__lables__', dumps_data(labels))

    print("Flushing database ...")
    db.sync()
    db.close()


if __name__ == "__main__":
    # generate lmdb
    # folder2lmdb("/mnt/data/th/FedTH/data/dataset/cinic10", name="train")
    folder2lmdb("/mnt/data/th/FedTH/data/dataset/covid/COVID-19_Radiography_Dataset", name="train")
    folder2lmdb("/mnt/data/th/FedTH/data/dataset/covid/COVID-19_Radiography_Dataset", name="test")