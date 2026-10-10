#include "rail_train_direction_math.h"
#include <iostream>
#include <string>
int main() {
    using namespace ch::rail_train_heading;
    const float xy[8][2] = {
        {1,0}, {1,1}, {0,1}, {-1,1},
        {-1,0}, {-1,-1}, {0,-1}, {1,-1}};
    for(int i=0;i<8;++i) {
        if(octant(xy[i][0],xy[i][1],ch::CameraRotation::r0)!=i) {
            std::cerr << "Wrong 8-way yaw bin: " << i << "\n";
            return 1;
        }
    }
    if(octant(1,0,ch::CameraRotation::r90)!=6 ||
       octant(1,0,ch::CameraRotation::r180)!=4 ||
       octant(1,0,ch::CameraRotation::r270)!=2 ||
       std::string(label(1))!="north_east" ||
       !is_diagonal(1) || is_diagonal(2)) {
        std::cerr << "Wrong CH_CAMERA_V1 eight-way mapping\n";
        return 2;
    }
    std::cout << "CH_RAIL_8_VIEW_DIRECTION_V1 PASS\n";
    return 0;
}
