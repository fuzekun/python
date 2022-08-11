'''
255代表白色，就是内容

    1. 读取图像，灰度化处理，二值化处理（基于大基算法）
    2. 进行图像的形态学操作，最后得到抠出了前景的背景图片，就只剩下轮廓的图片。
    3. 调整
        1. 需要进行角度的调整，否则行分割难以进行，裂分个也是这样。
        2. 进行bfs进行滤波
    3. 将图像进行上下切割得到ISBN号码，
        3.1 计算水平方向像素点的个数，进行边界分割，如何判断第几行是所需要的(0,1,2)
        3.2 根据像素点的个数进行分割
        3.2 计算竖直方向的个数，分割出单个字符。
    4. 进行数字的识别
    方法一 : 4.1 识别出图像的边缘，(使用canny算法)
            4.2 使用图形学的基元匹配

'''
import math

import cv2 as cv
import numpy as np
from pathlib import Path
import os
def show(name, img) :                        #方便展示图片，方便测试，运行的时候注释掉
    cv.namedWindow(name, cv.WINDOW_NORMAL)    #防止图片太大放不下
    cv.imshow(name, img)
    cv.waitKey(0)
    cv.destroyAllWindows();

color = 255                            #确定背景图片是0还是1
def transpos(image):
    (h, w) = image.shape[:2]
    (cX, cY) = (w // 2, h // 2)

    # 逆时针以图像中心旋转45度
    # - (cX,cY): 旋转的中心点坐标
    # - 45: 旋转的度数，正度数表示逆时针旋转，而负度数表示顺时针旋转。
    # - 1.0：旋转后图像的大小，1.0原图，2.0变成原来的2倍，0.5变成原来的0.5倍
    # OpenCV不会自动为整个旋转图像分配空间，以适应帧。旋转完可能有部分丢失。如果您希望在旋转后使整个图像适合视图，则需要进行优化，使用imutils.rotate_bound.
    M = cv.getRotationMatrix2D((cX, cY), 5, 1.0)
    rotated = cv.warpAffine(image, M, (w, h))
    show("Rotated by 5 Degrees", rotated)
    return rotated

def addBounder(image) :                  #给图像增加边框
    (tx, ty) = image.shape
    ret = np.zeros((tx + 10, ty + 10), np.uint8)
    (rx, ry) = (tx + 10, ty + 10)
    for i in range(rx):                                     #补上一圈白色像素
        for j in range(ry):
            if i < 5 or i >= tx + 5 or j < 5 or j >= ty + 5:
                ret[i][j] = 255
            else :
                ret[i][j] = image[i - 5][j - 5]
    return ret
def preHandle(imgPath) :                #图像的预处理
    img = cv.imread(imgPath)
    gray = cv.cvtColor(img, cv.COLOR_RGB2GRAY)  # 灰度化
    # 二值化
    ret1, thresh = cv.threshold(gray, 100, 255, cv.THRESH_BINARY_INV + cv.THRESH_OTSU ) #使用大基算法，将图像进行二值化
    # save(thresh)

    ret = addBounder(thresh)                   #增加边框
    # show('preImage', ret)
    return ret

# 将存储区域特别小的改成0
def changeTo0(img, tmp) :
    for (x, y) in tmp:
        img[x, y] = 0

# 找联通区域，返回联通区域的最低值
def bfs(grid, x, y, vis, tmpa) :                #tmpa保存内容
    dir = [(-1, 0), (1, 0), (0, -1), (0, 1)    # 上下左右
        , (-1, -1), (1, -1), (-1, 1), (1, 1)]  # 左上下，右上下
    (m, n) = grid.shape
    top = m
    bottom = 0
    left = n
    right = 0
    que = [(x, y)]
    tmpa.append((x, y))
    while len(que) > 0 :
        (x, y) = que.pop(0)                    #取出队列头
        for (dirx, diry) in dir :
            nx = x + dirx
            ny = y + diry
            if nx >= 0 and nx < m and ny >= 0 and ny < n and vis[nx][ny] == 0 and grid[nx][ny] == 255:
                bottom = max(bottom, nx)
                top = min(top, nx)
                left = min(left, ny)
                right = max(right, ny)
                que.append((nx, ny))
                tmpa.append((nx, ny))
                vis[nx][ny] = 1
    return (top, bottom, left, right)

def bfs2(grid, x, y, vis, cnts) :                       #cnts保存数量
    dir = [(-1, 0), (1, 0), (0, -1), (0, 1)  # 上下左右
        , (-1, -1), (1, -1), (-1, 1), (1, 1)]  # 左上下，右上下
    (m, n) = grid.shape
    top = m
    bottom = 0
    left = n
    right = 0
    que = [(x, y)]
    cnt = 0
    while len(que) > 0 :
        (x, y) = que.pop(0)                    #取出队列头
        for (dirx, diry) in dir :
            nx = x + dirx
            ny = y + diry
            if nx >= 0 and nx < m and ny >= 0 and ny < n and vis[nx][ny] == 0 and grid[nx][ny] == 255:
                bottom = max(bottom, nx)
                top = min(top, nx)
                left = min(left, ny)
                right = max(right, ny)
                que.append((nx, ny))
                cnt += 1
                vis[nx][ny] = 1
    cnts.append(cnt)
    return (top, bottom, left, right)


"""
     :param image: 预处理之后的图像
     :param thresh: 去噪声的阈值
     :return: 返回旋转的角度 
"""
def findConnection(image, thresh) :                   # 找到角度进行旋转
    recs = []                                         # 保存两个字符
    (maxx, maxy) = image.shape
    vis = np.zeros((maxx + 5, maxy + 5))
    # 去除边框
    tmpb = []
    bfs(image, 0, 0, vis, tmpb)
    changeTo0(image, tmpb)

    for i in range(maxx):                               #找到前两个边界值
        for j in range(maxy):
            if image[i][j] == 255 and vis[i][j] == 0:
                tmpa = []
                rec = bfs2(image, i, j, vis, tmpa)          # 连通区域的边界
                # print("lena = " + str(len(tmpa)))
                if tmpa[0] > thresh:                        # 如果不是噪声点
                    recs.append(rec)                        # 保存每个字符的边界
                    if len(recs) >= 2 : break               # 找到前两个字符就行
        if len(recs) >= 2 : break
    tanx = (recs[1][0] - recs[0][0]) / (recs[1][2] - recs[0][2])
    degree = np.arctan(tanx) * 180 / math.pi
    return degree


def getBounder(image, thresh) :                     #由findC..变形而来，找旋转后字符的上下边界
    (maxx, maxy) = image.shape
    vis = np.zeros((maxx + 5, maxy + 5))
    bottom = 0
    top = maxx
                                                    #可能需要再一次进行预处理
    for i in range(maxx):
        flag = 0                                    # 判断是否是二维码
        for j in range(maxy):
            if image[i][j] == 255 and vis[i][j] == 0:
                tmpa = []
                rec = bfs(image, i, j, vis, tmpa)          # 联通区域的边界
                # print("n_lena = " + str(len(tmpa)))
                if len(tmpa) > thresh:                     # 如果不是噪声点
                    if bottom != 0 and rec[1] > 1.5 * bottom :           # 如果是二维码
                        # print("扫描到二维码啦!")
                        flag = 1
                        break
                    top = min(top, rec[0])
                    bottom = max(bottom, rec[1])
                else :                                     # 如果是噪声点，去噪
                    changeTo0(image, tmpa)
        if flag == 1:
            break
    return (top, bottom)


def transpos(image, degree):                                #将图像进行旋转
    (h, w) = image.shape[:2]
    (cX, cY) = (w // 2, h // 2)

    M = cv.getRotationMatrix2D((cX, cY), degree, 1.0)
    rotated = cv.warpAffine(image, M, (w, h))
    # show("Rotated by x Degrees", rotated)
    return rotated


def cutLine(image, rec):
    img  = image[rec[0]:rec[1], :]
    # show('line', img)
    return img

def cutColumn(image, thresh) :                  # 使用bfs进行列切割(上到下，左到右)
    (maxx, maxy) = image.shape
    vis = np.zeros((maxx + 5, maxy + 5))
    recs = []                                   # 保存每一个图像的边界
    for i in range(maxx):                                  # 找到前两个边界值
        for j in range(maxy):
            if image[i][j] == 255 and vis[i][j] == 0:
                tmpa = []
                rec = bfs2(image, i, j, vis, tmpa)          # 连通区域的边界
                # print("lena = " + str(len(tmpa)))
                if tmpa[0] > thresh:                        # 如果不是噪声点
                    recs.append(rec)                        # 保存每个字符的边界
    recs.sort(key = lambda x:x[2])                          # 根据列进行排序                                #
    imgs = []
    # cnt = 0                                               # 展示计数
    for rec in recs:                                        # 得到每一列
        img = image[rec[0]:rec[1], rec[2]:rec[3]]
        imgs.append(img)
        # show(str(cnt), img)
        # cnt += 1
    return imgs





def classify(normData, dataSet, labels, k):
    # 计算行数
    dataSetSize = dataSet.shape[0]
    #     print ('dataSetSize 长度 =%d'%dataSetSi  ；                  vzvz ze)
    # 当前点到所有点的坐标差值  ,np.tile(x,(y,1)) 复制x 共y行 1列
    diffMat = np.tile(normData, (dataSetSize, 1)) - dataSet
    # 对每个坐标差值平方
    sqDiffMat = diffMat ** 2
    # 对于二维数组 sqDiffMat.sum(axis=0)指 对向量每列求和，sqDiffMat.sum(axis=1)是对向量每行求和,返回一个长度为行数的数组
    # 例如：narr = array([[ 1.,  4.,  6.],
    #                   [ 2.,  5.,  3.]])
    #    narr.sum(axis=1) = array([ 11.,  10.])
    #    narr.sum(axis=0) = array([ 3.,  9.,  9.])
    sqDistances = sqDiffMat.sum(axis=1)
    # 欧式距离 最后开方
    distance = sqDistances ** 0.5
    # x.argsort() 将x中的元素从小到大排序，提取其对应的index 索引，返回数组
    # 例：   tsum = array([ 11.,  10.])    ----  tsum.argsort() = array([1, 0])
    sortedDistIndicies = distance.argsort()
    #     classCount保存的K是魅力类型   V:在K个近邻中某一个类型的次数
    classCount = {}
    for i in range(k):
        # 获取对应的下标的类别
        voteLabel = labels[sortedDistIndicies[i]]
        # 给相同的类别次数计数
        classCount[voteLabel] = classCount.get(voteLabel, 0) + 1
    # sorted 排序 返回新的list
    #     sortedClassCount = sorted(classCount.items(),key=operator.itemgetter(1),reverse=True)
    sortedClassCount = sorted(classCount.items(), key=lambda x: x[1], reverse=True)
    return sortedClassCount[0][0]

def img2vector(image):
    # 创建一个1行1024列的矩阵
    returnVect = np.zeros((1, 1024))
    # 每个图像中有32行，每行有32列数据，遍历32个行，将2个列数据放入1024的列中
    for i in range(32):
        line = image[i]
        for j in range(32):
            returnVect[0, 32 * i + j] = int(line[j])
    return returnVect

"""
    1. 读取训练集TainData目录下所有文件和文件夹
    2. 将训练集的数据映射到1024维的空间中去
    3. 将测试的数字映射到1024维的空间中去
    4. 选取5个距离最近的排序,选择最近的作为数字
"""
def readTrain(trainingMat) :                                     #获取训练集合,返回训练集和标签
    labels = []
    trainingFileList = os.listdir('TrainData')
    m = len(trainingFileList)
    # print(m)
    for i in range(m):
        fileNameStr =  trainingFileList[i]                      # 文件名
        fileStr = fileNameStr.split('.')[0]                     # 前缀名
        classNumStr = (fileStr.split('_')[0])                   # 对应的字符
        labels.append(classNumStr)
        returnVect = np.zeros((1, 1024))                        # 创建一个向量
        fr = open('TrainData/' + fileNameStr, "r")              # 读取文件
        for j in range(32):                                     # 转化为1024行的向量
            lineStr = fr.readline()
            for k in range(32):
                returnVect[0, 32 * j + k] = int(lineStr[k])
        trainingMat[i, :] = returnVect                          # 存入对应的训练集
    return labels

 # 将图片保存为txt图像
def save(name, img) :            # 将像素数组放入文件中
    # print("文件保存中...")
    file = open(name, 'w')        # 自动创建文件,如果已经有了则覆盖，区别'x'
    (x, y) = img.shape
    for i in range(x):
        for j in range(y) :
            file.write(str(img[i, j])) #保存为二值图像
        if i != x - 1:      #最后一行不用保存
            file.write('\n')
    # print("保存完成")

# 将图片缩小为32 * 32的，然后进行二值化，最后保存到文件中
def changToTxt(image) :              # 返回一个32 * 32的二值图
    img = cv.resize(image, (32, 32), interpolation = cv.INTER_AREA)
    ret1, thresh = cv.threshold(img, 100, 1, cv.THRESH_BINARY_INV + cv.THRESH_OTSU)
    return thresh

def IdentifImg(images, names, trainingMat, labels, totalNum):     # 测试数据的图像对应数字以及训练集
    errorCount = 0
    mTest = min(len(images), len(names))
    expectList = ['I', 'S', 'B', 'N', '-']
    for i in range(mTest):
        img = images[i]
        # show(str(i), img)
        img = changToTxt(img)                           # 将图片归一化为32 * 32的
        # print('TestData/' + names[i] + '_1.txt')
        # save('TestData/' + names[i] + '_1.txt', img)
        if names[i] in expectList :
            continue
        vectorUnderTest = img2vector(img)               # 将图片转化为向量
        classifierResult = classify(vectorUnderTest, trainingMat, labels, 5)    # 分类
        # print("识别出的字符是: %c, 真实字符是: %c" % (classifierResult, names[i]))
        if (classifierResult != names[i]):
            errorCount += 1.0
    # print("\n识别错误次数 %d" % errorCount)
    errorRate = errorCount / float(totalNum)
    print("正确率: %f" % (1 - errorRate))
    return errorCount


# 将图片保存为txt图像
def save(name, img) :            # 将像素数组放入文件中
    print("文件保存中...")
    file = open(name, 'w')        # 自动创建文件,如果已经有了则覆盖，区别'x'
    (x, y) = img.shape
    for i in range(x):
        for j in range(y) :
            file.write(str(1 if img[i][j] > 0 else 0)) #保存为二值图像
        if i != x - 1:      #最后一行不用保存
            file.write('\n')
    print("保存完成")



def getName(names) :                                         #获取图片名称
    namelist = []
    for name in names:
        if name != ' ':
            namelist.append(name)
    return namelist

def getCount(names):                                        #获取数字有多少个
    cnt = 0
    expectList = [' ', 'I', 'S', 'B', 'N', '-']
    for name in names:
        if name not in expectList:
            cnt += 1
    return cnt

def printTrain(trainingMat) :                               #输出训练集
    for line in trainingMat:
        for v in line:
            print(v, end = " ")
        print()



if __name__ == '__main__':
    trainingMat = np.zeros((16, 1024))  # 15个模板,每个1024列
    labels = readTrain(trainingMat)     # 获取训练集，以及对应的标签
    print("训练集读取完成")

    errorNum = 0                                        #分割出错导致的错误的数量
    errorT = 0                                          #全部错误
    rightT = 0                                          #识别正确的字符
    total = 0                                           #总字符的个数
    trainingFileList = os.listdir('images')             #读取images下的文件
    m = len(trainingFileList)
    # fw = open('wrongName.txt', 'w')                     #打开文件，写入错误的名称和错误率
    # fw2 = open('wrongln', 'w')                          #写入错误的分割数量的图片

    for i in range(m):
        print('第%d章图片' % i)
        pic = trainingFileList[i]                       # 图片名称
        img = preHandle("images/" + pic)
        # show('pre', img)
        degree = findConnection(img, 50)
        # print("角度 = " + str(degree))
        rotated = transpos(img, degree)                 #将图像进行旋转
        # show('rotated', rotated)
        rec = getBounder(rotated, 50)                   #获取旋转图像的左右边界
        # print("top = " + str(rec[0]) + ' bottom = ' + str(rec[1]))
        img = cutLine(rotated, rec)
        # show('line', img)
        imgs = cutColumn(img, 50)                       #获取每一个数字
        prename = pic.split('.')[0]                     #前缀
        names = getName(prename)                        #获取每一个字符实际是多少
        totalNum = getCount(prename)                    #获取总共有多少数字
        # print('imgs.len = %d, names.len = %d' % (len(imgs), len(names)))
        if len(imgs) != len(names) :
            print("分割数量出错")
            # fw2.write(pic)
            # fw2.write('\n')
        errorCount = IdentifImg(imgs, names, trainingMat, labels, totalNum)
        total += len(names) - 4
        if errorCount > 0 :
            # fw.write(pic)
            # fw.write('\n')
            errorT += 1
        tmpright = totalNum - errorCount          # 需要减去4个才能是正确的个数
        print("正确个数为:%d" % tmpright)
        rightT += tmpright                               # 识别正确的个数

    # fw.close()
    # fw2.close()
    print("总体识别错误次数 %d" % errorT)
    errorRate = errorT / float(m)
    print("总体正确率: %f" % (1 - errorRate))
    rightRate = rightT / float(total)
    print("单个正确率: %f" % rightRate)
