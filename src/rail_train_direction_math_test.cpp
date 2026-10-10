#include "rail_train_direction_math.h"
#include <array>
#include <cmath>
#include <iostream>
#include <limits>
#include <string_view>

int main() {
    using namespace ch::rail_train_heading;
    constexpr std::array<std::array<float,2>,8> xy{{
        {{1,0}}, {{1,1}}, {{0,1}}, {{-1,1}},
        {{-1,0}}, {{-1,-1}}, {{0,-1}}, {{1,-1}}
    }};
    constexpr std::array<std::string_view,8> names{{
        "north", "north_east", "east", "east_south",
        "south", "south_west", "west", "west_north"
    }};
    for (int i=0;i<8;++i) {
        if (octant(xy[i][0],xy[i][1],ch::CameraRotation::r0)!=i ||
            std::string_view(label(i))!=names[i] ||
            is_diagonal(i)!=(i%2==1)) {
            std::cerr<<"Incorrect CH_CAMERA_V1 octant "<<i<<"\n";
            return 1;
        }
        // The same heading should choose the same art at any positive speed.
        if (octant(3*xy[i][0],3*xy[i][1],ch::CameraRotation::r0)!=i) {
            std::cerr<<"Direction changes with train velocity at "<<i<<"\n";
            return 2;
        }
        // Reversing a segment must reverse the art by exactly four views.
        if (octant(-xy[i][0],-xy[i][1],ch::CameraRotation::r0)!=(i+4)%8) {
            std::cerr<<"Opposite direction mismatch at "<<i<<"\n";
            return 3;
        }
    }
    for (const auto rotation : {ch::CameraRotation::r0, ch::CameraRotation::r90,
                                ch::CameraRotation::r180, ch::CameraRotation::r270}) {
        for (const auto& v:xy) {
            const int d=octant(v[0],v[1],rotation);
            if (d<0 || d>7 || std::string_view(label(d)).empty()) return 4;
        }
    }
    if (octant(1,0,ch::CameraRotation::r90)!=6 ||
        octant(1,0,ch::CameraRotation::r180)!=4 ||
        octant(1,0,ch::CameraRotation::r270)!=2) return 5;
    // An invalid heading must never index outside the eight-entry sprite array.
    const float nan=std::numeric_limits<float>::quiet_NaN();
    const float inf=std::numeric_limits<float>::infinity();
    if (octant(0,0,ch::CameraRotation::r0)!=0 ||
        octant(nan,1,ch::CameraRotation::r0)!=0 ||
        octant(inf,1,ch::CameraRotation::r0)!=0) return 6;
    std::cout<<"CH_RAIL_8_VIEW_DIRECTION_V2 PASS: 8 views, reverse, rotation, speed, invalid headings\n";
    return 0;
}
