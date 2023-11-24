import platform
import time

from PIL import ImageGrab


def z(f):
    def y(*x):
        start_time = time.time()
        f(*x)  # 被包装的对象
        stop_time = time.time()
        delta_time = stop_time - start_time
        return print("{:.9f}".format(delta_time))

    return y


if platform.system() == "Windows":
    import win32api
    import win32con
    import win32gui
    import win32ui

    @z
    def window_capture(filename, r, c, w, h):
        # 窗口的编号，0号表示当前活跃窗口
        hwnd = 0
        # 根据窗口句柄获取窗口的设备上下文Divice Context
        hwndDC = win32gui.GetWindowDC(hwnd)
        # 根据窗口的DC获取mfcDC
        mfcDC = win32ui.CreateDCFromHandle(hwndDC)
        # mfcDC创建可兼容的DC
        saveDC = mfcDC.CreateCompatibleDC()
        # 创建bigmap准备保存图片
        saveBitMap = win32ui.CreateBitmap()
        # 获取监控器信息
        MoniterDev = win32api.EnumDisplayMonitors()
        print("显示器坐标系:{}".format(MoniterDev[0][-1]))
        # 为bitmap开辟空间
        saveBitMap.CreateCompatibleBitmap(mfcDC, w, h)
        # 高度saveDC，将截图保存到saveBitmap中
        saveDC.SelectObject(saveBitMap)
        # 截取从左上角（0，0）长宽为（w，h）的图片
        saveDC.BitBlt((0, 0), (w, h), mfcDC, (r, c), win32con.SRCCOPY)
        # 保存截取的图片
        saveBitMap.SaveBitmapFile(saveDC, filename)

    window_capture("./2.png", 0, 0, 1980, 1024)

else:

    @z
    def python_capture(filename, *place):
        screen = ImageGrab.grab()
        print("显示分辨率:{}".format(screen.size))
        img = ImageGrab.grab(bbox=place)
        img.save(filename)

    python_capture("./2.png", 0, 0, 1980, 1024)
