import cv2
import numpy as np
import dlib
import time
import math
import threading

detector = dlib.get_frontal_face_detector()
predictor = dlib.shape_predictor("./FaceRecognition/shape_predictor_68_face_landmarks.dat")
POINTS_NUM_LANDMARK = 68

class Orientation():
    def __init__(self):
        self.FaceState=-1
        self.StopSign=False
        self.DrawEnable=True
        self.RoleRegion=[]
    
        self.CAPID = 0
        while(1):
            cap = cv2.VideoCapture(self.CAPID,cv2.CAP_DSHOW)
            ret, frame = cap.read()
            if ret == False:
                self.CAPID += 1
            else:
                break

    def enable(self):
        self.T=threading.Thread(target=self.FaceDetection)
        self.T.start()
    def start(self):
        self.StopSign=False
        try:
            if not self.T.is_alive():
                cv2.destroyAllWindows()
                cv2.waitKey(1)
                self.T=threading.Thread(target=self.FaceDetection)
                self.T.start()
        except:
            pass
    def stop(self):
        self.StopSign=True
        

    def Region_append(self,divide,select):
        self.RoleRegion.append([divide,select])

    def GetSize(self):
        return self.Size

    def GetState(self):
        return self.FaceState

    # 用dlib检测关键点，返回姿态估计需要的几个点坐标
    def get_image_points(self,img):
        dets = detector( img, 0 )
        if 0 == len( dets ):
            return False,None
        largest_index =  self._largest_face(dets)
        face_rectangle = dets[largest_index]
        landmark_shape = predictor(img, face_rectangle)
        return  self.get_image_points_from_landmark_shape(landmark_shape)

    # 获取最大的人脸
    def _largest_face(self,dets):
        if len(dets) == 1:
            return 0
        face_areas = [ (det.right()-det.left())*(det.bottom()-det.top()) for det in dets]
        largest_area = face_areas[0]
        largest_index = 0
        for index in range(1, len(dets)):
            if face_areas[index] > largest_area :
                largest_index = index
                largest_area = face_areas[index]
        return largest_index

    # 从dlib的检测结果抽取姿态估计需要的点坐标
    def get_image_points_from_landmark_shape(self,landmark_shape):
        if landmark_shape.num_parts != POINTS_NUM_LANDMARK:
            return False, None
        image_points = np.array([
                                    (landmark_shape.part(30).x, landmark_shape.part(30).y),     # Nose tip
                                    (landmark_shape.part(8).x, landmark_shape.part(8).y),     # Chin
                                    (landmark_shape.part(36).x, landmark_shape.part(36).y),     # Left eye left corner
                                    (landmark_shape.part(45).x, landmark_shape.part(45).y),     # Right eye right corne
                                    (landmark_shape.part(48).x, landmark_shape.part(48).y),     # Left Mouth corner
                                    (landmark_shape.part(54).x, landmark_shape.part(54).y)      # Right mouth corner
                                ], dtype="double")
        return True, image_points

    # 获取旋转向量和平移向量                        
    def get_pose_estimation(self,img_size, image_points ):
        model_points = np.array([
                                    (0.0, 0.0, 0.0),             # Nose tip
                                    (0.0, -330.0, -65.0),        # Chin
                                    (-225.0, 170.0, -135.0),     # Left eye left corner
                                    (225.0, 170.0, -135.0),      # Right eye right corne
                                    (-150.0, -150.0, -125.0),    # Left Mouth corner
                                    (150.0, -150.0, -125.0)      # Right mouth corner
                                
                                ])
        focal_length = img_size[1]
        center = (img_size[1]/2, img_size[0]/2)
        camera_matrix = np.array(
                                [[focal_length, 0, center[0]],
                                [0, focal_length, center[1]],
                                [0, 0, 1]], dtype = "double"
                                )
        dist_coeffs = np.zeros((4,1)) # Assuming no lens distortion
        (success, rotation_vector, translation_vector) = cv2.solvePnP(model_points, image_points, camera_matrix, dist_coeffs, flags=cv2.SOLVEPNP_ITERATIVE )
        return success, rotation_vector, translation_vector, camera_matrix, dist_coeffs

    # 从旋转向量转换为欧拉角
    def get_euler_angle(self,rotation_vector):
        theta = cv2.norm(rotation_vector, cv2.NORM_L2)
        w = math.cos(theta / 2)
        x = math.sin(theta / 2)*rotation_vector[0][0] / theta
        y = math.sin(theta / 2)*rotation_vector[1][0] / theta
        z = math.sin(theta / 2)*rotation_vector[2][0] / theta
        ysqr = y * y
        t0 = 2.0 * (w * x + y * z)
        t1 = 1.0 - 2.0 * (x * x + ysqr)
        pitch = math.atan2(t0, t1)
        t2 = 2.0 * (w * y - z * x)
        if t2 > 1.0:
            t2 = 1.0
        if t2 < -1.0:
            t2 = -1.0
        yaw = math.asin(t2)
        t3 = 2.0 * (w * z + x * y)
        t4 = 1.0 - 2.0 * (ysqr + z * z)
        roll = math.atan2(t3, t4)
        Y = int((pitch/math.pi)*180)
        X = int((yaw/math.pi)*180)
        Z = int((roll/math.pi)*180)
        return Y, X, Z
        
    def FaceDetection(self):
        cap = cv2.VideoCapture(self.CAPID,cv2.CAP_DSHOW)
        start_time = time.time()
        while (cap.isOpened()) and not self.StopSign:
            ret1, im = cap.read()
            
            if ret1!=True:
                print("读取相机画面失败")
                continue
            
            size = im.shape
            if size[0] > 700:
                h = size[0] / 3
                w = size[1] / 3
                im = cv2.resize( im, (int( w ), int( h )), interpolation=cv2.INTER_CUBIC )
                size = im.shape
            self.Size=size
            ret2,image_points = self.get_image_points(im)
            pitch, yaw, roll=0,0,0
            nose_point=[0,0]
            ret=False
            if ret2:
                ret3, rotation_vector, translation_vector, camera_matrix, dist_coeffs =  self.get_pose_estimation(size, image_points)
                (nose_end_point2D, jacobian) = cv2.projectPoints(np.array([(0.0, 0.0, 1000.0)]), rotation_vector, translation_vector, camera_matrix, dist_coeffs)
                if ret3:
                    pitch, yaw, roll =  self.get_euler_angle(rotation_vector)
                    nose_point = ( int(nose_end_point2D[0][0][0]), int(nose_end_point2D[0][0][1]))
                    ret=True

            state=self.judgment(nose_point[0],nose_point[1],ret)
            if state!=self.FaceState:
                if time.time() - start_time > 0.5:
                    self.FaceState=state
            else:
                start_time = time.time()
            if self.DrawEnable:
                self.draw(pitch, yaw, roll,image_points,nose_point,size,ret,im)
            time.sleep(0.05)

    def judgment(self,x,y,sate):
        self.RoleRegion
        if sate:
            for role in self.RoleRegion:
                Region=role[0]
                if x>=Region[0] and x<=Region[2] and y>=Region[1] and y<=Region[3]:
                    return role[1]
        return -1

    def draw(self,pitch, yaw, roll,image_points,nose_point,size,ret,im):
        if ret:
            im = np.zeros(size, np.uint8)
            im.fill(255)
            for p in image_points:
                cv2.circle(im, (int(p[0]), int(p[1])), 3, (0,0,255), -1)
            p1 = ( int(image_points[0][0]), int(image_points[0][1]))
            cv2.line(im, p1, nose_point, (255,0,0), 2)
        else:
            im = np.zeros(size, np.uint8)
            im.fill(10)
        cv2.putText( im, 'Rotate Y:{}, X:{}, Z:{}'.format(pitch, yaw, roll), (10, 20), cv2.FONT_HERSHEY_PLAIN, 1, (0, 0, 255), 1 )
        cv2.putText( im, "Position X:{} Y:{}".format(nose_point[0],nose_point[1]),(10, 40), cv2.FONT_HERSHEY_PLAIN, 1, (0, 0, 255), 1 )
        cv2.putText( im, "Size H:{} W:{}".format(size[0],size[1]), (10, 60), cv2.FONT_HERSHEY_PLAIN, 1, (0, 0, 255), 1 )
        cv2.putText( im, "state:"+str(self.FaceState), (10, 80), cv2.FONT_HERSHEY_PLAIN, 1, (0, 0, 255), 1 )
        cv2.imshow("Output", im)
        cv2.waitKey(1)

if __name__ == '__main__':
    A=Orientation()
    A.Region_append([0,0,360,480],0)
    A.Region_append([360,0,640,480],1)
    A.enable()
    
