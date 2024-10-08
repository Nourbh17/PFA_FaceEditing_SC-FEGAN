# -*- coding: utf-8 -*-
"""Data_preparation_loading.ipynb

Automatically generated by Colab.

Original file is located at
    https://colab.research.google.com/drive/1uu5h56pIJ3ZB7aOTO2oZTT5lUsLAf6ps

THIS IS THE ONE
"""

from google.colab import drive
drive.mount('/content/drive')
# %cd "/content/drive/MyDrive/PFA"

import os

# path ="celebahq/CelebAMask-HQ/CelebA-HQ-img/color"

!pip install tensorflow-io
# print('installed succ cd next')

# %cd "/content/drive/MyDrive/PFA/"
# print('cd done classes next')

import numpy as np
import cv2 as cv
from face_toolbox_keras_master.models.parser.BiSeNet.bisenet import BiSeNet_keras

FILE_PATH = "/content/drive/MyDrive/PFA/face_toolbox_keras_master/models/parser"


class FaceParser():
    def __init__(self, path_bisenet_weights=FILE_PATH + "/BiSeNet/BiSeNet_keras.h5", detector=None):
        self.parser_net = None
        self.detector = detector
        self.build_parser_net(path_bisenet_weights)

    def build_parser_net(self, path):
        parser_net = BiSeNet_keras()
        parser_net.load_weights(path)
        self.parser_net = parser_net

    def set_detector(self, detector):
        self.detector = detector

    def remove_detector(self):
        self.detector = None

    def parse_face(self, im, bounding_box=None, with_detection=False):
        orig_h, orig_w = im.shape[:2]

        # Detect/Crop face RoI
        if bounding_box == None:

            faces = [im]
        else:
            x0, y0, x1, y1 = bounding_box
            x0, y0 = np.maximum(x0, 0), np.maximum(y0, 0)
            x1, y1 = np.minimum(x1, orig_h), np.minimum(y1, orig_w)
            x0, y0, x1, y1 = map(np.int32, [x0, y0, x1, y1])
            faces = [im[x0:x1, y0:y1, :]]

        maps = []
        for face in faces:
            # Preprocess input face for parser networks
            orig_h, orig_w = face.shape[:2]
            inp = cv.resize(face, (512, 512))
            inp = self.normalize_input(inp)
            inp = inp[None, ...]

            # Parser networks forward pass
            # Do NOT use bilinear interp. which adds artifacts to the parsing map
            out = self.parser_net.predict([inp])[0]
            parsing_map = out.argmax(axis=-1)
            parsing_map = cv.resize(
                parsing_map.astype(np.uint8),
                (orig_w, orig_h),
                interpolation=cv.INTER_NEAREST)
            maps.append(parsing_map)
        return maps

    @staticmethod
    def normalize_input(x, mean=(0.485, 0.456, 0.406), std=(0.229, 0.224, 0.225)):
        # x should be RGB with range [0, 255]
        return ((x / 255) - mean) / std

!pip install MTCNN

import math
import cv2 as cv
from PIL import Image
import os
import numpy as np
import tensorflow as tf
from mtcnn.mtcnn import MTCNN

import tensorflow_io as tfio

detector = MTCNN()


class load_data():
    def __init__(self, path_image):
        self.image = path_image


    def hair_mask(self,pic):
        parser = FaceParser()
        img = pic[..., ::-1]
        parsed = parser.parse_face(img, with_detection=False)
        component_mask = np.zeros(tuple(img.shape[:-1]))
        component_mask[parsed[0] == 17] = 1
        component_mask = np.reshape(component_mask, (img.shape[0], img.shape[1], 1))
        return component_mask.astype("float32")

    def get_color(self,pic):
        annotation_colors = [
            '0, background', '1, skin', '2, left eyebrow', '3, right eyebrow',
            '4, left eye', '5, right eye', '6, glasses', '7, left ear', '8, right ear', '9, earings',
            '10, nose', '11, mouth', '12, upper lip', '13, lower lip',
            '14, neck', '15, neck_l', '16, cloth', '17, hair', '18, hat']

        parser = FaceParser()
        img = pic[..., ::-1]
        parsed = parser.parse_face(img, with_detection=False)

        # blurring image
        img = cv.cvtColor(img, cv.COLOR_BGR2RGB)
        imgg = cv.medianBlur(img, 5)
        bilateral = imgg
        for i in range(20):
            bilateral = cv.bilateralFilter(bilateral, 20, 30, 30)
        median_image = np.zeros(bilateral.shape)
        for i in range(len(annotation_colors)):
            component_mask = np.zeros(tuple(pic.shape[:-1]))
            component_mask[parsed[0] == i] = 1
            masked = np.multiply(cv.cvtColor(
                bilateral, cv.COLOR_RGB2BGR), np.expand_dims(component_mask, axis=-1))
            median_image += masked
        median_image = median_image.astype(np.uint8)
        median_image = cv.cvtColor(median_image, cv.COLOR_BGR2RGB)
        return median_image

    def edges_detection(self,pic):
        (H, W) = pic.shape[:2]
        blob = cv.dnn.blobFromImage(pic, scalefactor=1.0, size=(W, H),
                                    swapRB=False, crop=False)
        file= "deploy.prototxt"
        caf = "hed_pretrained_bsds.caffemodel"

        net = cv.dnn.readNetFromCaffe(file, caf)
        net.setInput(blob)
        hed = net.forward()
        hed = cv.resize(hed[0, 0], (pic.shape[0], pic.shape[1]))
        hed = (255 * hed).astype("uint8")
        ret2, th2 = cv.threshold(hed, 0, 255, cv.THRESH_BINARY + cv.THRESH_OTSU)
        binary_mask = np.reshape(th2, (pic.shape[0], pic.shape[1], 1))
        return binary_mask.astype(np.uint8)

    def create_mask(self, pic, number_of_mask=3):
        panel_mask = np.zeros((pic.shape[0], pic.shape[1], 1), dtype="float32")
        faces = detector.detect_faces(pic)
        if len(faces) == 0:
            # Handle the case where no faces are detected
            print("No faces detected")
            return None
        x1, y1, width, height = faces[0]["box"]
        x2, y2 = x1 + width, y1 + height
        binary_mask = np.zeros((y2 - y1, x2 - x1, 1), dtype="int32")

        for i in range(number_of_mask):
            start_x = np.random.randint(0, x2 - x1)
            start_y = np.random.randint(0, y2 - y1)
            start_angle = np.random.randint(180)
            numV = np.random.randint(80, 100)
            for j in range(numV):
                angleP = np.random.randint(-15, 15)
                if j % 2 == 0:
                    angle = start_angle + angleP
                else:
                    angle = start_angle + angleP + 180
                length = np.random.randint(80, 100)
                end_x = start_x + int(length * math.cos(math.radians(angle)))
                end_y = start_y + int(length * math.sin(math.radians(angle)))

                cv.line(binary_mask, (start_x, start_y), (end_x, end_y), 255, 15)
                start_x = end_x
                start_y = end_y

        panel_mask[y1:y2, x1:x2] = binary_mask[:, :]
        hair_mask_num = np.random.randint(2, 8)
        if hair_mask_num > 5:
            hair_mask = self.hair_mask(pic)
            panel_mask += hair_mask
        panel_mask = np.where(np.clip(panel_mask, 0., 255.) == 0, 0., 255.)/255.
        return panel_mask.astype("uint8")

    def get_data(self ):
        pic = cv.imread(self.image)

        pic = cv.resize(pic, (512, 512))
        pic = cv.cvtColor(pic, cv.COLOR_BGR2RGB)
        # pic = Image.open(self.image).convert('RGB')
        # pic = cv.resize(pic, (512, 512))
        binary_mask = self.create_mask(pic)
        sketch = self.edges_detection(pic)
        color = self.get_color(pic)
        noise = np.random.normal(size=(pic.shape[0], pic.shape[1], 1))
        reversed_mask = 1 - binary_mask
        input_image = pic * reversed_mask
        sketch = sketch * binary_mask
        color = color * binary_mask
        noise = noise * binary_mask
        return pic, input_image, sketch, color, binary_mask * 255, noise

import tensorflow as tf

class Data_Preparation():
    def __init__(self, folder_path):
        self.last = False
        self.nb=0
        self.names = []
        self.path = folder_path
        self.label, self.total_images, self.total_sketch, self.total_color, self.total_mask, self.total_noise = \
            self.data_load(0,100)
        self.ground_truth, self.total_input = self.data_batch()
        self.incomplete_image = self.total_input[:][..., 0:3]
        self.sketch = self.total_input[:][..., 3:4]
        self.color = self.total_input[:][..., 4:7]
        self.mask = self.total_input[:][..., 7:8]
        self.noise = self.total_input[:][..., 8:9]
        self.batch_data = [self.incomplete_image, self.sketch, self.color, self.mask, self.noise]

    def data_load(self,start,end ):
        true_sketch = []
        true_img = []
        images = []
        colors = []
        edges = []
        masks = []
        noises = []
        if not self.names:
            self.names = [name for name in os.listdir(self.path + "color")]

        # for name in images_name:
        for i in range(start,end):
            true_img.append(self.path +"truth/"  + self.names[i])
            images.append(self.path + "input/" +  self.names[i])
            edges.append(self.path + "sketch/"+   self.names[i])
            colors.append(self.path + "color/" +  self.names[i])
            masks.append(self.path + "mask/" +  self.names[i])
            noises.append(self.path +"noise/" +  self.names[i])
        self.nb += 1
        return true_img, images, edges, colors, masks, noises

    def getNext(self):
        start = self.nb*100
        end = start+100
        if (len(self.names)- end < 0 ):
            end = len(self.names)
            self.last = True
        self.label, self.total_images, self.total_sketch, self.total_color, self.total_mask, self.total_noise = \
            self.data_load(start,end)
        self.ground_truth, self.total_input = self.data_batch()
        self.incomplete_image = self.total_input[:][..., 0:3]
        self.sketch = self.total_input[:][..., 3:4]
        self.color = self.total_input[:][..., 4:7]
        self.mask = self.total_input[:][..., 7:8]
        self.noise = self.total_input[:][..., 8:9]
        self.batch_data = [self.incomplete_image, self.sketch, self.color, self.mask, self.noise]

    def data_batch(self, ):
        total_label = []
        total_batch = []
        for i in range(len(self.total_sketch)):
            actual = tf.image.decode_jpeg(tf.io.read_file(self.label[i]), channels=3)
            actual = tfio.experimental.color.bgr_to_rgb(actual)
            actual = (tf.cast(actual, dtype=tf.float32) / 127.5) - 1.0

            pic = tf.image.decode_jpeg(tf.io.read_file(self.total_images[i]), channels=3)
            pic = tfio.experimental.color.bgr_to_rgb(pic)
            pic = (tf.cast(pic, dtype=tf.float32) / 127.5 )- 1.0

            sketch = tf.image.decode_jpeg(tf.io.read_file(self.total_sketch[i]), channels=1)
            sketch = tf.where(sketch > 150,255.,0.)
            sketch = tf.cast(sketch, dtype=tf.float32) / 255.

            color = tf.image.decode_jpeg(tf.io.read_file(self.total_color[i]), channels=3)
            color = tfio.experimental.color.bgr_to_rgb(color)
            color = (tf.cast(color, dtype=tf.float32) / 127.5 )- 1.0

            mask = tf.image.decode_jpeg(tf.io.read_file(self.total_mask[i]), channels=1)
            mask = tf.where(mask > 150,255.,0.)
            mask = tf.cast(mask, dtype=tf.float32) / 255.

            noise = tf.image.decode_jpeg(tf.io.read_file(self.total_noise[i]), channels=1)
            noise = tf.cast(noise, dtype=tf.float32) / 255.

            batch_input = tf.concat([pic, sketch, color, mask, noise], axis=-1)
            total_batch.append(batch_input)
            total_label.append(actual)

        total_batch = tf.stack(total_batch, axis=0)
        total_label = tf.stack(total_label, axis=0)
        return total_label, total_batch

