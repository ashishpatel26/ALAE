import zipfile
import tqdm
from defaults import get_cfg_defaults
import sys
import logging

from dlutils import download

from scipy import misc
from net import *
import numpy as np
import pickle
import random
import argparse
import os
from dlutils.pytorch.cuda_helper import *
import tensorflow as tf


def prepare_mnist(cfg, logger):
    im_size = 32

    dlutils.download.mnist()
    mnist = dlutils.reader.Mnist('mnist').items
    mnist_images = np.asarray([x[1] for x in mnist], np.uint8)
    mnist_labels = np.asarray([x[0] for x in mnist], np.uint8)

    mnist_images = F.pad(torch.tensor(mnist_images).view(mnist_images.shape[0], 1, 28, 28), (2, 2, 2, 2)).detach().cpu().numpy()

    directory = os.path.dirname(cfg.DATASET.PATH)

    os.makedirs(directory, exist_ok=True)

    folds = cfg.DATASET.PART_COUNT
    mnist_folds = [[] for _ in range(folds)]

    count = len(mnist)

    count_per_fold = count // folds
    for i in range(folds):
        mnist_folds[i] += (mnist_images[i * count_per_fold: (i + 1) * count_per_fold],
                           mnist_labels[i * count_per_fold: (i + 1) * count_per_fold])

    for i in range(folds):
        images = mnist_folds[i][0]
        labels = mnist_folds[i][1]
        tfr_opt = tf.python_io.TFRecordOptions(tf.python_io.TFRecordCompressionType.NONE)
        part_path = cfg.DATASET.PATH % (2 + 3, i)
        tfr_writer = tf.python_io.TFRecordWriter(part_path, tfr_opt)

        for image, label in zip(images, labels):
            ex = tf.train.Example(features=tf.train.Features(feature={
                'shape': tf.train.Feature(int64_list=tf.train.Int64List(value=image.shape)),
                'label': tf.train.Feature(int64_list=tf.train.Int64List(value=[label])),
                'data': tf.train.Feature(bytes_list=tf.train.BytesList(value=[image.tostring()]))}))
            tfr_writer.write(ex.SerializeToString())
        tfr_writer.close()

        for j in range(5):
            images_down = []

            for image, label in zip(images, labels):
                h = image.shape[1]
                w = image.shape[2]
                image = torch.tensor(np.asarray(image, dtype=np.float32)).view(1, 1, h, w)

                image_down = F.avg_pool2d(image, 2, 2).clamp_(0, 255).to('cpu', torch.uint8)

                image_down = image_down.view(1, h // 2, w // 2).numpy()
                images_down.append(image_down)

            part_path = cfg.DATASET.PATH % (5 - j - 1, i)
            tfr_writer = tf.python_io.TFRecordWriter(part_path, tfr_opt)
            for image, label in zip(images_down, labels):
                ex = tf.train.Example(features=tf.train.Features(feature={
                    'shape': tf.train.Feature(int64_list=tf.train.Int64List(value=image.shape)),
                    'label': tf.train.Feature(int64_list=tf.train.Int64List(value=[label])),
                    'data': tf.train.Feature(bytes_list=tf.train.BytesList(value=[image.tostring()]))}))
                tfr_writer.write(ex.SerializeToString())
            tfr_writer.close()

            images = images_down


def run():
    parser = argparse.ArgumentParser(description="Adversarial, hierarchical style VAE")
    parser.add_argument(
        "--config-file",
        default="configs/experiment_mnist.yaml",
        metavar="FILE",
        help="path to config file",
        type=str,
    )
    parser.add_argument(
        "opts",
        help="Modify config options using the command-line",
        default=None,
        nargs=argparse.REMAINDER,
    )

    args = parser.parse_args()
    cfg = get_cfg_defaults()
    cfg.merge_from_file(args.config_file)
    cfg.merge_from_list(args.opts)
    cfg.freeze()

    logger = logging.getLogger("logger")
    logger.setLevel(logging.DEBUG)

    output_dir = cfg.OUTPUT_DIR
    os.makedirs(output_dir, exist_ok=True)

    ch = logging.StreamHandler(stream=sys.stdout)
    ch.setLevel(logging.DEBUG)
    formatter = logging.Formatter("%(asctime)s %(name)s %(levelname)s: %(message)s")
    ch.setFormatter(formatter)
    logger.addHandler(ch)
    logger.info(args)

    logger.info("Loaded configuration file {}".format(args.config_file))
    with open(args.config_file, "r") as cf:
        config_str = "\n" + cf.read()
        logger.info(config_str)
    logger.info("Running with config:\n{}".format(cfg))

    prepare_mnist(cfg, logger)


if __name__ == '__main__':
    run()

