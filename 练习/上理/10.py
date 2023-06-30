<<<<<<< HEAD
=======
# Copyright 2017 Google Inc


>>>>>>> a98794fef118e4fbd47d0348edb5f8b3154dd000
import struct
from struct import unpack
from PIL import Image, ImageDraw
import os


class QuickDrawing:
    """
    Represents a single Quick, Draw! drawing.
    """

    def __init__(self, name, drawing_data):
        self._name = name
        self._drawing_data = drawing_data
        self._strokes = None
        self._image = None

    @property
    def name(self):
        """
        Returns the name of the drawing (anvil, aircraft, ant, etc).
        """
        return self._name

    @property
    def key_id(self):
        """
        Returns the id of the drawing.
        """
        return self._drawing_data["key_id"]

    @property
    def countrycode(self):
        """
        Returns the country code for the drawing.
        """
        return self._drawing_data["countrycode"].decode("utf-8")

    @property
    def recognized(self):
        """
        Returns a boolean representing whether the drawing was recognized.
        """
        return bool(self._drawing_data["recognized"])

    @property
    def timestamp(self):
        """
        Returns the time the drawing was created (in seconds since the epoch).
        """
        return self._drawing_data["timestamp"]

    @property
    def no_of_strokes(self):
        """
        Returns the number of pen strokes used to create the drawing.
        """
        return self._drawing_data["n_strokes"]

    @property
    def image_data(self):
        """
        Returns the raw image data as list of strokes with a list of X
        co-ordinates and a list of Y co-ordinates.
        Co-ordinates are aligned to the top-left hand corner with values
        from 0 to 255.
        See https://github.com/googlecreativelab/quickdraw-dataset#simplified-drawing-files-ndjson
        for more information regarding how the data is represented.
        """
        return self._drawing_data["image"]

    @property
    def strokes(self):
        """
        Returns a list of pen strokes containing a list of (x,y) coordinates which make up the drawing.
        To iterate though the strokes data use::

            from quickdraw import QuickDrawData
            qd = QuickDrawData()
            anvil = qd.get_drawing("anvil")
            for stroke in anvil.strokes:
                for x, y in stroke:
                    print("x={} y={}".format(x, y))
        """

        if self._strokes is None:

            self._strokes = []
            for stroke in self.image_data:
                points = []
                xs = stroke[0]
                ys = stroke[1]

                if len(xs) != len(ys):
                    raise Exception("something is wrong, different number of x's and y's")

                for point in range(len(xs)):
                    x = xs[point]
                    y = ys[point]
                    points.append((x, y))
                self._strokes.append(points)

        return self._strokes

    @property
    def image(self):
        """
        Returns a `PIL Image <https://pillow.readthedocs.io/en/3.0.x/reference/Image.html>`_
        object of the drawing on a white background with a black drawing. Alternative image
        parameters can be set using ``get_image()``.
        To save the image you would use the ``save`` method::
            from quickdraw import QuickDrawData
            qd = QuickDrawData()
            anvil = qd.get_drawing("anvil")
            anvil.image.save("my_anvil.gif")

        """
        if self._image is None:
            self._image = self.get_image()

        return self._image

    def get_image(self, stroke_color=(0, 0, 0), stroke_width=2, bg_color=(255, 255, 255)):
        """
        Get a `PIL Image <https://pillow.readthedocs.io/en/3.0.x/reference/Image.html>`_
        object of the drawing.
        :param list stroke_color:
            A list of RGB (red, green, blue) values for the stroke color,
            defaults to (0,0,0).
        :param int stroke_color:
            A width of the stroke, defaults to 2.
        :param list bg_color:
            A list of RGB (red, green, blue) values for the background color,
            defaults to (255,255,255).
        """
        image = Image.new("RGB", (255, 255), color=bg_color)
        image_draw = ImageDraw.Draw(image)

        for stroke in self.strokes:
            image_draw.line(stroke, fill=stroke_color, width=stroke_width)

        return image

    def __str__(self):
        return "QuickDrawing key_id={}".format(self.key_id)


def unpack_drawing(file_handle):
    key_id, = unpack('Q', file_handle.read(8))
    country_code, = unpack('2s', file_handle.read(2))
    recognized, = unpack('b', file_handle.read(1))
    timestamp, = unpack('I', file_handle.read(4))
    n_strokes, = unpack('H', file_handle.read(2))
    image = []
    for i in range(n_strokes):
        n_points, = unpack('H', file_handle.read(2))
        fmt = str(n_points) + 'B'
        x = unpack(fmt, file_handle.read(n_points))
        y = unpack(fmt, file_handle.read(n_points))
        image.append((x, y))

    return {
        'key_id': key_id,
        'country_code': country_code,
        'recognized': recognized,
        'timestamp': timestamp,
        'image': image
    }


def unpack_drawings(filename):
    with open(filename, 'rb') as f:
        while True:
            try:
                yield unpack_drawing(f)
            except struct.error:
                break


def load_bin_files(dir):
    fileslist = []
    for path, dirs, files in os.walk(dir):
        for file in files:
            fileslist.append(os.path.join(path, file))
    return fileslist


if __name__ == "__main__":
    bin_fileslist = load_bin_files('W:\\桌面\QuickDraw\\10')
    datasetdir = 'W:\\桌面\\QuickDraw\\png'
    if not os.path.exists(datasetdir):
        os.mkdir(datasetdir)

    for binfile in bin_fileslist:
        class_name = binfile[binfile.rindex('\\') + 1: binfile.rindex('.bin')]
        print(binfile, " ", class_name)

        class_dir = os.path.join(datasetdir, class_name)
        if not os.path.exists(class_dir):
            os.mkdir(class_dir)

        index = 0
        for drawing in unpack_drawings(binfile):
            qt = QuickDrawing(class_name, drawing)
            image = qt.get_image()
            image.save(os.path.join(class_dir, str(index) + '.png'))
            index = index + 1