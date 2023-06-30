import os
import time
import warnings
import inspect
import tifffile
import numpy as np
import matplotlib.pyplot as plt
from abc import ABC, abstractmethod
from scipy.signal import convolve
from ZernikeOptics import ZernikeWavefront, PsfGenerator3D, present


class Object3D(ABC):
    registered = {}

    @classmethod
    def register(cls, object_subclass):
        issubclass(object_subclass, cls) or present(
            ValueError("not a object subclass"))
        cls.registered[object_subclass.__name__.lower()] = object_subclass

    @classmethod
    def instantiate(cls, **kwargs):
        'object_name' in kwargs or present(ValueError("object name missing"))
        object_name = str(kwargs['object_name']).lower()
        object_name in cls.registered or present(
            ValueError("object not registered"))
        object_subclass = cls.registered[object_name]
        init_keys = inspect.signature(
            object_subclass.__init__).parameters.keys()
        init_kwargs = {
            k: kwargs[k]
            for k in init_keys if k != 'name' and k in kwargs
        }
        return object_subclass(**init_kwargs)

    def __init__(self, shape):
        self.shape = shape
        len(self.shape) == 3 or present(
            ValueError("only 3d object are supported"))
        self.object = np.zeros(self.shape)

    def check_object(self):
        if np.sum(self.object) <= 0:
            warnings.warn("no any object created")

    @abstractmethod
    def generate(self):
        pass

    @abstractmethod
    def get(self):
        pass


class Points(Object3D):
    """
        Creates multiple points
        :param shape: tuple, object shape as (z, y, x), e.g. (64, 64, 64)
        :param num: integer, number of points, e.g. 3
        :param center: boolean, whether to have a point at the center, default is True
        :param pad_from_boundary: integer, leave space between points and boundary.
               Helpful for convolution, recommended size // 5
    """

    def __init__(self, shape, num, center=True, pad_from_boundary=0):
        super().__init__(shape)
        self.num = num
        self.center = center
        self.pad_from_boundary = pad_from_boundary
        self.generate()

    def generate(self):
        _num = self.num
        np.isscalar(
            self.pad_from_boundary
        ) and self.pad_from_boundary < np.min(self.shape) // 2 or present(
            ValueError(
                "padding from boundary has to be scalar and bounded by object size"
            ))

        _xp = np.zeros(self.shape, np.float32)
        if self.center:
            _xp[self.shape[0] // 2, self.shape[1] // 2,
                self.shape[2] // 2] = 1.
            _num = _num - 1
        _i, _j, _k = np.random.randint(
            self.pad_from_boundary,
            (np.min(self.shape) - self.pad_from_boundary), (3, _num))
        _xp[_i, _j, _k] = 1.

        self.object = _xp
        self.check_object()

    def get(self):
        self.check_object()
        return self.object


class Sphere(Object3D):
    """
        Creates 3d sphere
        :param shape: tuple, object shape as (z, y, x), e.g. (64, 64, 64)
        :param units: tuple, voxel size in microns, e.g. (0.1, 0.1, 0.1)
        :param radius: scalar, radius of sphere in microns, e.g. 0.75
        :param off_centered: tuple, displacement vector by which center is moved as (k, j, i) e.g. (0.5, 0.5, 0.5)
    """

    def __init__(self, shape, units, radius, off_centered=(0, 0, 0)):
        super().__init__(shape)
        self.shape = shape
        self.units = units
        self.radius = radius
        self.off_centered = off_centered
        self.generate()

    def generate(self):
        isinstance(self.off_centered, tuple) or present(
            ValueError("displacement vector for center is not a 3d vector"))
        if isinstance(self.radius, (list, tuple)):
            self.radius = np.random.choice(self.radius)
        np.isscalar(self.radius) or present(
            ValueError("radius has to be scalar"))
        all(2 * self.radius < _u * _s
            for _u, _s in zip(self.units, self.shape)) or present(
                ValueError("object diameter is bigger than object shape"))

        _xs = list(u * (np.arange(s) - s / 2)
                   for u, s in zip(self.units, self.shape))
        _xs = tuple(_x - self.off_centered[_i] for _i, _x in enumerate(_xs))
        gz, gy, gx = np.meshgrid(*_xs, indexing="ij")
        r = np.sqrt(gx**2 + gy**2 + gz**2)
        masked_r = 1. * (r <= self.radius)

        self.object = masked_r
        self.check_object()

    def get(self):
        self.check_object()
        return self.object


class Images(Object3D):
    """
        Creates 3d sphere
        :param shape: tuple, object shape as (z, y, x), e.g. (64, 64, 64)
        :param filepath: string, filepath, e.g. W:/.../.../1.tif
    """

    def __init__(self, shape, filepath):
        super().__init__(shape)
        self.shape = shape
        self.image = tifffile.imread(filepath)
        self.generate()

    def generate(self):
        if self.image.ndim in (3, 4):
            present('need gray image not rgb image')
        else:
            data = (self.image - self.image.min()) / (self.image.max() -
                                                      self.image.min())
            self.object = data * np.ones(self.shape)

        self.check_object()

    def get(self):
        self.check_object()
        return self.object


Object3D.register(Points)
Object3D.register(Sphere)
Object3D.register(Images)


class Noises:
    """
        Add noise to data
        :param image: 3d array as image
        :param snr: scalar or tuple, signal to noise ratio
        :param mean: scalar or tuple, mean background noise
        :param sigma: scalar or tuple, sigma for gaussian noise
        :param rg: function, aim is give a number of range
        :return: 3d array
    """

    def __init__(self, image, mean, sigma, snr, rg=None):
        super().__init__(Noises)
        self.image = image
        self.mean = mean
        self.sigma = sigma
        self.snr = snr
        self.rg = rg

    # 添加高斯噪声
    def add_normal_noise(self):
        noise = np.random.normal(self.mean, self.sigma,
                                 self.image.shape) + self.image
        return noise

    # 添加泊松噪声
    def add_poisson_noise(self):
        noise = np.random.poisson(
            np.maximum(1, self.image * self.snr + 1).astype(int)).astype(
                np.float32)
        return noise

    # 添加组合的高斯噪声和泊松噪声
    def add_normal_poisson_noise(self):
        noise = self.add_normal_noise() + self.add_poisson_noise()
        return noise

    def add_random_noise(self):
        if self.rg is None:
            self.rg = np.random.uniform
        np.isscalar(self.snr) or present(
            ValueError("please give a snr value range"))
        np.isscalar(self.mean) or present(
            ValueError("please give a mean value range"))
        np.isscalar(self.sigma) or present(
            ValueError("please give a sigma value range"))
        all(v[0] <= v[1]
            for v in [self.snr, self.mean, self.sigma]) or present(
                ValueError(
                    "Lower bound is expected to be less than the upper bound"))
        all(v[0] >= 0 and v[1] >= 0
            for v in [self.snr, self.mean, self.sigma]) or present(
                ValueError(
                    "Noise's parameter is expected to be greater than 0"))

        self.mean = self.rg(*self.mean)
        self.sigma = self.rg(*self.sigma)
        self.snr = self.rg(*self.snr)
        self.image = (self.image - np.min(self.image)) / (np.max(self.image) +
                                                          np.min(self.image))

        noise = self.add_normal_poisson_noise()
        noise = np.maximum(0, noise)
        noise = np.minimum(1, noise)
        return noise


def cropper(image, crop_shape, jitter=False, max_jitter=None, planes=None):
    """
        Crops 3d data
        :param image: 3d array, image to be cropped
        :param crop_shape: tuple, crop shape
        :param jitter: boolean, randomly move the center point within a given limit, default is False
        :param max_jitter: tuple, maximum displacement for jitter, if None then it gets a default value
        :param planes: scalar, get a crop image plane
        :return: 3d array
    """

    half_crop_shape = tuple(_c // 2 for _c in crop_shape)
    half_image_shape = tuple(_i // 2 for _i in image.shape)
    assert all([_c <= _i for _c, _i in zip(half_crop_shape, half_image_shape)
                ]), "Crop shape is bigger than image shape"

    if jitter:
        contrain_1 = tuple(
            (_i - _c) // 4
            for _c, _i in zip(half_crop_shape, half_image_shape))
        contrain_2 = tuple(c // 2 for c in half_crop_shape)
        if max_jitter is None:
            max_jitter = tuple([
                min(_ct2, _ct1) for _ct2, _ct1 in zip(contrain_1, contrain_2)
            ])
        all([
            _i - _m >= 0 and _i + _m < 2 * _i
            for _m, _i in zip(max_jitter, half_image_shape)
        ]) or present(
            ValueError(
                "Jitter results in cropping outside border, please reduce max_jitter"
            ))
        loc = tuple(_l - np.random.randint(-1 * max_jitter[_i], max_jitter[_i])
                    for _i, _l in enumerate(half_image_shape))
    else:
        loc = half_image_shape

    crop_image = image[loc[0] - half_crop_shape[0]:loc[0] + half_crop_shape[0],
                       loc[1] - half_crop_shape[1]:loc[1] + half_crop_shape[1],
                       loc[2] - half_crop_shape[2]:loc[2] + half_crop_shape[2]]

    if planes is not None:
        try:
            crop_image = crop_image[planes]
        except IndexError:
            present(ValueError("Plane does not exist"))

    return crop_image


if __name__ == '__main__':
    # 设置所需泽尼克模式字典
    # -------------------------------------------------------------------------------------------------------------- #
    zernike_nm = {
        'defocus': (2, 0),
        'astig_vert': (2, -2),
        'astig_obli': (2, 2),
        'astig_2th_vert': (4, -2),
        'astig_2th_obli': (4, 2),
        'coma_vert': (3, -1),
        'coma_obli': (3, 1),
        'coma_2th_vert': (5, -1),
        'coma_2th_obli': (5, 1),
        'spher_1st': (4, 0),
        'spher_2st': (6, 0),
        'spher_3st': (8, 0),
        'spher_4st': (10, 0),
        'trefo_vert': (3, -3),
        'trefo_obli': (3, 3),
        'trefo_2th_vert': (4, -4),
        'trefo_2th_obli': (4, 4),
    }

    all_mode_name = zernike_nm.keys()

    # 设置程序工作模式
    # -------------------------------------------------------------------------------------------------------------- #
    """
    模式1：多目标生成单模式 Aberration, Psf 和 Psf Object
    模式2：多目标生成混合模式 Aberration, Psf 和 Psf Object
    模式3：单目标按照 Sted 显微镜的 SLM 精度生成单模式 Aberration 与 Psf
    模式4：单目标最大最小像差范围随机均匀采样生成 Aberration, Psf 和 Psf Object
    模式5：生成特定的单个 Aberration 与 Psf
    """

    mode = 2

    # 设置数据存储路径
    # -------------------------------------------------------------------------------------------------------------- #

    file_db = '/Volumes/昊大侠/工作/上海理工大学/论文/小论文/超分辨成像/数据集/data_label/data'
    if not os.path.exists(file_db):
        os.makedirs(file_db)
    file_db1 = f'{file_db}/Aberration_data'
    if not os.path.exists(file_db1):
        os.makedirs(file_db1)
    file_db2 = f'{file_db}/Psf_data'
    if not os.path.exists(file_db2):
        os.makedirs(file_db2)

    # 程序各个模式的执行逻辑
    # -------------------------------------------------------------------------------------------------------------- #
    if mode == 1:
        data_folder = "/Users/WangHao/Desktop/data_4_20"
        folderList = os.listdir(data_folder)

        try:
            folderList.remove('.DS_Store')
        except:
            pass
        try:
            folderList.remove('._.DS_Store')
        except:
            pass

        sample_all_dict = {}

        for folder in folderList:
            sample_list = []
            data_list = os.listdir(os.path.join(data_folder, folder))
            print(f'the number of {folder} is: {len(data_list)}.')

            for datas_fn in data_list:
                sample_list.append(os.path.join(data_folder, folder, datas_fn))

            sample_all_dict[f'{folder}'] = sample_list

        for folder, sample_list in sample_all_dict.items():
            for sample in sample_list:
                if data_folder.split("/")[-1][0:-5] == "label":
                    dshape = (15, 256, 256)
                    object_params = {
                        'object_name': 'images',
                        'shape': dshape,
                        'filepath': sample
                    }
                    dsize = (0.1, 0.12, 0.12)
                else:
                    dshape = (15, 128, 128)
                    object_params = {
                        'object_name': 'images',
                        'shape': dshape,
                        'filepath': sample
                    }
                    dsize = (0.1, 0.12, 0.12)
                if folder == "ER":
                    wave_length = 560
                else:
                    wave_length = 488

                the_object = Object3D.instantiate(**object_params)
                obj = the_object.get()
                range = wave_length / 4
                nm_amp = {
                    v: np.arange(-range, range, 2 * range / 1000)
                    for _, v in zernike_nm.items()
                }
                start1 = time.time()
                for i, (key, value) in enumerate(nm_amp.items()):
                    mode_name = list(all_mode_name)[i]
                    start2 = time.time()
                    for j, v in enumerate(value):
                        zwf = ZernikeWavefront({key: v}, order='ansi')
                        psf = PsfGenerator3D(psf_shape=dshape,
                                             units=dsize,
                                             na_detection=1.7,
                                             lam_detection=wave_length,
                                             n=1.518)

                        zwf_xy = zwf.polynomial(dshape[-1],
                                                normed=True,
                                                outside=0)
                        psf_zxy = psf.incoherent_psf_intensity(zwf,
                                                               normed=True)

                        psf_obj = []
                        for idx in range(dshape[0]):
                            psf_obj.append(
                                convolve(obj[idx]**2, psf_zxy[idx], 'same'))

                        index_news = list(zwf.zernikes.keys())

                        zwf_save_dir_base = os.path.join(file_db1, folder)
                        if not os.path.exists(zwf_save_dir_base):
                            os.makedirs(zwf_save_dir_base)
                        zwf_xy_save_dir = os.path.join(
                            zwf_save_dir_base,
                            f'{mode_name}_{v:.4f}_{index_news[0].index_ansi}_{j}_zwf_xy'
                        )

                        np.save(zwf_xy_save_dir, zwf_xy)
                        plt.imsave(f'{zwf_xy_save_dir}.png', zwf_xy, dpi=300)

                        psf_save_dir_base = os.path.join(file_db2, folder)
                        if not os.path.exists(psf_save_dir_base):
                            os.makedirs(psf_save_dir_base)
                        psf_zxy_save_dir = os.path.join(
                            psf_save_dir_base,
                            f'{mode_name}_{v:.4f}_{index_news[0].index_ansi}_{j}_psf_zxy'
                        )

                        np.save(psf_zxy_save_dir, psf_zxy)
                        for k, img in enumerate(psf_zxy):
                            plt.imsave(f'{psf_zxy_save_dir}_{k}.png',
                                       img,
                                       dpi=300)

                        psf_obj_save_dir = os.path.join(
                            psf_save_dir_base,
                            f'{mode_name}_{v:.4f}_{index_news[0].index_ansi}_{j}_psf_obj'
                        )

                        np.save(psf_obj_save_dir, psf_obj)
                        for k, img in enumerate(psf_obj):
                            plt.imsave(f'{psf_obj_save_dir}_{k}.png',
                                       img,
                                       dpi=300)

                    end2 = time.time()
                    print("运行时间:%.2f秒" % (end2 - start2))
                end1 = time.time()
                print("运行时间:%.2f秒" % (end1 - start1))

    elif mode == 2:
        data_folder = "/Users/WangHao/Desktop/data_4_20"
        folderList = os.listdir(data_folder)

        try:
            folderList.remove('.DS_Store')
        except:
            pass
        try:
            folderList.remove('._.DS_Store')
        except:
            pass

        sample_all_dict = {}

        for folder in folderList:
            sample_list = []
            data_list = os.listdir(os.path.join(data_folder, folder))
            print(f'the number of {folder} is: {len(data_list)}.')

            for datas_fn in data_list:
                sample_list.append(os.path.join(data_folder, folder, datas_fn))

            sample_all_dict[f'{folder}'] = sample_list

        start1 = time.time()
        for folder, sample_list in sample_all_dict.items():
            start2 = time.time()
            for _, sample in enumerate(sample_list):
                if data_folder.split("/")[-1][0:-5] == "label":
                    dshape = (15, 256, 256)
                    object_params = {
                        'object_name': 'images',
                        'shape': dshape,
                        'filepath': sample
                    }
                    dsize = (0.1, 0.12, 0.12)
                else:
                    dshape = (15, 128, 128)
                    object_params = {
                        'object_name': 'images',
                        'shape': dshape,
                        'filepath': sample
                    }
                    dsize = (0.1, 0.12, 0.12)
                if folder == "ER":
                    wave_length = 0.560
                else:
                    wave_length = 0.488

                the_object = Object3D.instantiate(**object_params)
                obj = the_object.get()

                index = sample.split("/")[-1][0:-4]

                range = wave_length / 4
                # 混合像差总目标系数
                all_amp = np.arange(-range, range, 2 * range / 1000)
                # 使其为正态分布的均值，从中抽样17个子目标系数
                all_amp_dict = {}
                for x in all_amp:
                    sub_amp_dict = {}
                    sub_amp = np.random.normal(
                        loc=x, scale=np.abs(2 * x), size=17) / 17
                    for j, (_, v) in enumerate(zernike_nm.items()):
                        sub_amp_dict[v] = sub_amp[j]
                    all_amp_dict[x] = sub_amp_dict

                all_amp_dict_save_dir_base = os.path.join(
                    file_db, "amplitude_dict")
                if not os.path.exists(all_amp_dict_save_dir_base):
                    os.makedirs(all_amp_dict_save_dir_base)
                all_amp_dict_save_dir = os.path.join(
                    all_amp_dict_save_dir_base, f"{folder}_{index}")
                np.save(all_amp_dict_save_dir, all_amp_dict)

                # 命名规则[细胞类型]/[数据类型]_[像差数值]_[ROI序号]_[像差序号]
                for i, (key, value) in enumerate(all_amp_dict.items()):
                    zwf = ZernikeWavefront(value, order='ansi')
                    psf = PsfGenerator3D(psf_shape=dshape,
                                         units=dsize,
                                         na_detection=1.7,
                                         lam_detection=wave_length,
                                         n=1.518)

                    zwf_xy = zwf.polynomial(dshape[-1], normed=True, outside=0)
                    psf_zxy = psf.incoherent_psf_intensity(zwf, normed=True)

                    psf_obj = []
                    for idx in np.arange(dshape[0]):
                        psf_obj.append(convolve(obj[idx], psf_zxy[idx],
                                                'same'))

                    zwf_save_dir_base = os.path.join(file_db1, folder)
                    if not os.path.exists(zwf_save_dir_base):
                        os.makedirs(zwf_save_dir_base)
                    zwf_xy_save_dir = os.path.join(
                        zwf_save_dir_base, f'zwf_xy_{key:.6f}_{index}_{i+1}')

                    np.save(zwf_xy_save_dir, zwf_xy)
                    # plt.imsave(f'{zwf_xy_save_dir}.png', zwf_xy, dpi=300)

                    psf_save_dir_base = os.path.join(file_db2, folder)
                    if not os.path.exists(psf_save_dir_base):
                        os.makedirs(psf_save_dir_base)
                    psf_zxy_save_dir = os.path.join(
                        psf_save_dir_base, f'psf_zxy_{key:.6f}_{index}_{i+1}')

                    np.save(psf_zxy_save_dir, psf_zxy)
                    # for k, img in enumerate(psf_zxy):
                    #     plt.imsave(f'{psf_zxy_save_dir}_{k}.png', img, dpi=300)

                    psf_obj_save_dir = os.path.join(
                        psf_save_dir_base, f'psf_obj_{key:.6f}_{index}_{i+1}')

                    np.save(psf_obj_save_dir, psf_obj)
                    # for k, img in enumerate(psf_obj):
                    #     plt.imsave(f'{psf_obj_save_dir}_{k}.png', img, dpi=300)

                end2 = time.time()
                print("运行时间:%.2f秒" % (end2 - start2))
        end1 = time.time()
        print("运行时间:%.2f秒" % (end1 - start1))

    elif mode == 3:
        # 按照 Sted 显微镜的 SLM 精度设置 (-0.5π， 0.5π) 的像差
        nm_amp = {
            v: np.arange(
                np.round(
                    -0.775 / 4 * 1. / np.sqrt(
                        (1. + (v[1] == 0)) / (2. * v[0] + 2)) / np.sqrt(np.pi),
                    3),
                np.round(
                    0.775 / 4 * 1. / np.sqrt(
                        (1. + (v[1] == 0)) / (2. * v[0] + 2)) / np.sqrt(np.pi),
                    3), 0.00025)
            for k, v in zernike_nm.items()
        }
        start1 = time.time()
        index_save_dir = os.path.join(file_db, 'all_mode_index')
        np.save(index_save_dir, nm_amp)
        for i, (key, value) in enumerate(nm_amp.items()):
            mode_name = list(all_mode_name)[i]
            start2 = time.time()
            for j, v in enumerate(value):
                zwf = ZernikeWavefront({key: v}, order='ansi')
                psf = PsfGenerator3D(psf_shape=(3, 129, 129),
                                     units=(0.1, 0.1, 0.1),
                                     na_detection=1.4,
                                     lam_detection=0.775,
                                     n=1.518)

                zwf_xy = zwf.polynomial(129, normed=True, outside=0)
                psf_zxy = psf.incoherent_psf(zwf, normed=True)

                # import matplotlib.pyplot as plot
                # plot.imshow(np.abs(psf_zxy[1, :, :]))
                # plot.show()

                index_news = list(zwf.zernikes.keys())

                zwf_save_dir_base = os.path.join(file_db1, mode_name)
                if not os.path.exists(zwf_save_dir_base):
                    os.makedirs(zwf_save_dir_base)
                zwf_xy_save_dir = os.path.join(
                    zwf_save_dir_base,
                    f'{mode_name}_{v:.5f}_{index_news[0].index_noll}_{j}_zwf_xy'
                )
                np.save(zwf_xy_save_dir, zwf_xy)

                psf_save_dir_base = os.path.join(file_db2, mode_name)
                if not os.path.exists(psf_save_dir_base):
                    os.makedirs(psf_save_dir_base)
                psf_zxy_save_dir = os.path.join(
                    psf_save_dir_base,
                    f'{mode_name}_{v:.5f}_{index_news[0].index_noll}_{j}_psf_zxy'
                )
                np.save(psf_zxy_save_dir, psf_zxy[1, :, :])

            end2 = time.time()
            print("运行时间:%.2f秒" % (end2 - start2))
        end1 = time.time()
        print("运行时间:%.2f秒" % (end1 - start1))

    elif mode == 4:
        object_params = {
            'object_name': 'sphere',
            'radius': 0.075,
            'shape': (121, 256, 256),
            'units': (0.032, 0.016, 0.016)
        }
        the_object = Object3D.instantiate(**object_params)
        obj = the_object.get()
        normamp = 0
        if normamp:
            # 归一化下的幅值对应的相差(-π, π)
            nm_amp = {
                v: np.round(np.random.uniform(-0.775 / 4, 0.775 / 4, 2000), 4)
                for k, v in zernike_nm.items()
            }
        else:
            # 未归一化的幅值对应的相差(-π, π)
            nm_amp = {
                v: np.arange(
                    np.round(
                        -0.775 / 4 * 1. / np.sqrt(
                            (1. + (v[1] == 0)) / (2. * v[0] + 2)) /
                        np.sqrt(np.pi), 3),
                    np.round(
                        0.775 / 4 * 1. / np.sqrt(
                            (1. + (v[1] == 0)) / (2. * v[0] + 2)) /
                        np.sqrt(np.pi), 3), 0.00025)
                for k, v in zernike_nm.items()
            }
        start1 = time.time()
        index_save_dir = os.path.join(file_db, 'seventeen_mode_index')
        np.save(index_save_dir, nm_amp)
        for i, (key, value) in enumerate(nm_amp.items()):
            mode_name = list(all_mode_name)[i]
            start2 = time.time()
            for j, v in enumerate(value):
                zwf = ZernikeWavefront({key: v}, order='ansi')
                psf = PsfGenerator3D(psf_shape=(121, 256, 256),
                                     units=(0.032, 0.016, 0.016),
                                     na_detection=1.4,
                                     lam_detection=0.775,
                                     n=1.518)

                zwf_xy = zwf.polynomial(256, normed=False, outside=0)
                psf_zxy = psf.incoherent_psf(zwf, normed=False)
                psf_obj = convolve(np.abs(obj)**2, psf_zxy, 'same')

                index_news = list(zwf.zernikes.keys())

                zwf_save_dir_base = os.path.join(file_db1, mode_name)
                if not os.path.exists(zwf_save_dir_base):
                    os.makedirs(zwf_save_dir_base)
                zwf_xy_save_dir = os.path.join(
                    zwf_save_dir_base,
                    f'{mode_name}_{v:.4f}_{index_news[0].index_noll}_{j}_zwf_xy'
                )
                np.save(zwf_xy_save_dir, zwf_xy)

                psf_save_dir_base = os.path.join(file_db2, mode_name)
                if not os.path.exists(psf_save_dir_base):
                    os.makedirs(psf_save_dir_base)
                psf_zxy_save_dir = os.path.join(
                    psf_save_dir_base,
                    f'{mode_name}_{v:.4f}_{index_news[0].index_noll}_{j}_psf_zxy'
                )
                np.save(psf_zxy_save_dir, psf_zxy)
                psf_obj_save_dir = os.path.join(
                    psf_save_dir_base,
                    f'{mode_name}_{v:.4f}_{index_news[0].index_noll}_{j}_psf_obj'
                )
                np.save(psf_obj_save_dir, psf_obj)

            end2 = time.time()
            print("运行时间:%.2f秒" % (end2 - start2))
        end1 = time.time()
        print("运行时间:%.2f秒" % (end1 - start1))

    elif mode == 5:

        start1 = time.time()

        zwf = ZernikeWavefront({(0, 0): 0}, order='ansi')
        psf = PsfGenerator3D(psf_shape=(3, 129, 129),
                             units=(0.1, 0.1, 0.1),
                             na_detection=1.4,
                             lam_detection=0.775,
                             n=1.518)

        zwf_xy = zwf.polynomial(129, normed=False, outside=0)
        psf_zxy = psf.incoherent_psf(zwf, normed=False)

        index_news = list(zwf.zernikes.keys())

        zwf_save_dir_base = os.path.join(file_db1, 'piston')
        if not os.path.exists(zwf_save_dir_base):
            os.makedirs(zwf_save_dir_base)
        zwf_xy_save_dir = os.path.join(
            zwf_save_dir_base,
            f'piston_{0:.5f}_{index_news[0].index_noll}_{0}_zwf_xy')
        np.save(zwf_xy_save_dir, zwf_xy)

        psf_save_dir_base = os.path.join(file_db2, 'piston')
        if not os.path.exists(psf_save_dir_base):
            os.makedirs(psf_save_dir_base)
        psf_zxy_save_dir = os.path.join(
            psf_save_dir_base,
            f'piston_{0:.5f}_{index_news[0].index_noll}_{0}_psf_zxy')
        np.save(psf_zxy_save_dir, psf_zxy[1, :, :])

        end1 = time.time()
        print("运行时间:%.2f秒" % (end1 - start1))
