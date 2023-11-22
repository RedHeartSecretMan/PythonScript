import json
import os

import cv2
import numpy as np


def adjust_pts_order(pts_2ds):
    """sort rectangle points by counterclockwise"""

    cen_x, cen_y = np.mean(pts_2ds, axis=0)
    # refer_line = np.array([10,0])

    d2s = []
    for i in range(len(pts_2ds)):
        o_x = pts_2ds[i][0] - cen_x
        o_y = pts_2ds[i][1] - cen_y
        atan2 = np.arctan2(o_y, o_x)
        if atan2 < 0:
            atan2 += np.pi * 2
        d2s.append([pts_2ds[i], atan2])

    d2s = sorted(d2s, key=lambda x: x[1])
    order_2ds = np.array([x[0] for x in d2s])

    return order_2ds


if __name__ == "__main__":
    folder_name = r"DYH-长轴静态斑块标注7-16"
    data_folder = f"/Users/WangHao/Desktop/TODO/Data/{folder_name}"
    save_folder = f"/Users/WangHao/Desktop/TODO/Data/{folder_name}/dataset"

    data_list = os.listdir(data_folder)
    try:
        data_list.remove(".DS_Store")
    except:
        pass
    try:
        data_list.remove("._.DS_Store")
    except:
        pass
    try:
        data_list.remove("dataset")
    except:
        pass

    for i in range(len(data_list)):
        data_img_label = os.listdir(os.path.join(data_folder, data_list[i]))
        try:
            data_img_label.remove(".DS_Store")
        except:
            pass
        try:
            data_img_label.remove("._.DS_Store")
        except:
            pass
        if len(data_img_label) <= 4:
            flag = 0
            for filename in data_img_label:
                if ".json" in filename:
                    flag = 1
                    break
            if flag == 1:
                for filename in data_img_label:
                    if ".json" in filename:
                        label = filename
                    if "image" in filename and ".json" not in filename:
                        image = filename
            else:
                for filename in data_img_label:
                    if "label" in filename:
                        label = filename
                    if "image" in filename:
                        image = filename

            img_dir = os.path.join(data_folder, data_list[i], image)
            cv_img = cv2.imdecode(np.fromfile(img_dir, dtype=np.uint8), -1)
            label_dir = os.path.join(data_folder, data_list[i], label)

            if flag == 1:
                with open(label_dir, "r") as f:
                    dict = json.load(f)

                shapes = dict["shapes"]

                front_outpoints = np.ndarray(shape=(0, 2), dtype=np.uint8)
                front_inpoints = np.ndarray(shape=(0, 2), dtype=np.uint8)

                for j in range(len(shapes)):
                    kind = shapes[j]["label"]
                    x = int(shapes[j]["points"][0][0])
                    y = int(shapes[j]["points"][0][1])
                    point = np.asarray([x, y])

                    if kind == "2":
                        front_outpoints = np.vstack((front_outpoints, point))
                    elif kind == "1":
                        front_inpoints = np.vstack((front_inpoints, point))
                    else:
                        raise ValueError(f"point label error: {kind}")

                front_outpoints = adjust_pts_order(front_outpoints)
                front_inpoints = adjust_pts_order(front_inpoints)

                if len(cv_img.shape) == 3:
                    label_img = np.zeros_like(cv_img)
                else:
                    cv_img = np.expand_dims(cv_img, axis=-1).repeat(axis=-1, repeats=3)
                    label_img = np.zeros_like(cv_img)

                # 填充
                cv2.fillPoly(label_img, pts=[front_outpoints], color=(0, 0, 255))  # R
                cv2.fillPoly(label_img, pts=[front_inpoints], color=(0, 255, 0))  # G
                # import matplotlib.pyplot as plot
                # plot.figure(1)
                # plot.imshow(cv_img)
                # plot.figure(2)
                # plot.imshow(label_img)
                # plot.show()

                # label_img = cv2.flip(label_img, 1)

                img_add = cv2.addWeighted(cv_img, 0.7, label_img, 0.3, 0)

                save_dir = os.path.join(save_folder, f"{folder_name}_{data_list[i]}")

                if not os.path.exists(save_dir):
                    os.makedirs(save_dir)

                cv2.imencode(".png", img_add)[1].tofile(
                    os.path.join(save_dir, "add.png")
                )

            else:
                label_img = cv2.imdecode(np.fromfile(label_dir, dtype=np.uint8), -1)

            save_dir = os.path.join(save_folder, f"{folder_name}_{data_list[i]}")

            if not os.path.exists(save_dir):
                os.makedirs(save_dir)

            cv2.imencode(".png", cv_img)[1].tofile(os.path.join(save_dir, "image.png"))
            cv2.imencode(".png", label_img)[1].tofile(
                os.path.join(save_dir, "label.png")
            )

        else:
            labels = []
            labels_1 = []
            labels_2 = []
            images = []

            for filename in data_img_label:
                if ".json" in filename:
                    labels_1.append(filename)
                if "label" in filename:
                    labels_2.append(filename)
                if "image" in filename and ".json" not in filename:
                    images.append(filename)

            if len(labels_1) == 2:
                labels = labels_1
            elif len(labels_1) == 1:
                numflag = labels_1[0].split(".")[0][-1:]
                for name in labels_2:
                    if numflag in name:
                        labels.append(labels_1[0])
                    else:
                        labels.append(name)
            else:
                labels = labels_2

            assert len(labels) == len(images)

            for k in range(len(labels)):
                label = labels[k]
                flag = 0
                if ".json" in label:
                    flag = 1
                for name in images:
                    if label.split(".")[0][5:] == name.split(".")[0][5:]:
                        image = name

                img_dir = os.path.join(data_folder, data_list[i], image)
                cv_img = cv2.imdecode(np.fromfile(img_dir, dtype=np.uint8), -1)
                label_dir = os.path.join(data_folder, data_list[i], label)

                if flag == 1:
                    with open(label_dir, "r") as f:
                        dict = json.load(f)

                    shapes = dict["shapes"]

                    front_outpoints = np.ndarray(shape=(0, 2), dtype=np.uint8)
                    front_inpoints = np.ndarray(shape=(0, 2), dtype=np.uint8)

                    for j in range(len(shapes)):
                        kind = shapes[j]["label"]
                        x = int(shapes[j]["points"][0][0])
                        y = int(shapes[j]["points"][0][1])
                        point = np.asarray([x, y])

                        if kind == "2":
                            front_outpoints = np.vstack((front_outpoints, point))
                        elif kind == "1":
                            front_inpoints = np.vstack((front_inpoints, point))
                        else:
                            raise ValueError(f"point label error: {kind}")

                    front_outpoints = adjust_pts_order(front_outpoints)
                    front_inpoints = adjust_pts_order(front_inpoints)

                    if len(cv_img.shape) == 3:
                        label_img = np.zeros_like(cv_img)
                    else:
                        cv_img = np.expand_dims(cv_img, axis=-1).repeat(
                            axis=-1, repeats=3
                        )
                        label_img = np.zeros_like(cv_img)

                    # 填充
                    cv2.fillPoly(
                        label_img, pts=[front_outpoints], color=(0, 0, 255)
                    )  # R
                    cv2.fillPoly(
                        label_img, pts=[front_inpoints], color=(0, 255, 0)
                    )  # G
                    # import matplotlib.pyplot as plot
                    # plot.figure(1)
                    # plot.imshow(cv_img)
                    # plot.figure(2)
                    # plot.imshow(label_img)
                    # plot.show()

                    # label_img = cv2.flip(label_img, 1)

                    img_add = cv2.addWeighted(cv_img, 0.7, label_img, 0.3, 0)

                    save_dir = os.path.join(
                        save_folder, f"{folder_name}_{data_list[i]}"
                    )

                    if not os.path.exists(save_dir):
                        os.makedirs(save_dir)

                    cv2.imencode(".png", img_add)[1].tofile(
                        os.path.join(save_dir, "add.png")
                    )

                else:
                    label_img = cv2.imdecode(np.fromfile(label_dir, dtype=np.uint8), -1)

                save_dir = os.path.join(
                    save_folder, f"{folder_name}_{data_list[i]}_{k}"
                )

                if not os.path.exists(save_dir):
                    os.makedirs(save_dir)

                cv2.imencode(".png", cv_img)[1].tofile(
                    os.path.join(save_dir, "image.png")
                )
                cv2.imencode(".png", label_img)[1].tofile(
                    os.path.join(save_dir, "label.png")
                )
