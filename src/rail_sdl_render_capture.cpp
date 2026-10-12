// CH_RAIL_SDL_RENDER_CAPTURE_V1
// Deterministic review of the SAME SDL production train sprite adapter and
// the SAME turntable sprite compositor used by city_builder. This is an
// instrumented SDL capture, not a recording of an interactive player session.
#include "rail_live_operation_controller.h"
#include "rail_placement_controller.h"
#include "rail_train_sprite_render_adapter.h"
#include "rail_turntable_sprite_runtime.h"
#include "src/ch_core/projection.h"

#include <SDL3/SDL.h>
#include <algorithm>
#include <array>
#include <fstream>
#include <limits>
#include <cmath>
#include <filesystem>
#include <iomanip>
#include <iostream>
#include <map>
#include <sstream>
#include <string>
#include <unordered_set>
#include <vector>

namespace {
constexpr int W=1000,H=600;
constexpr float PI=3.14159265358979323846F;
struct Frame {
    std::vector<ch::rail_operation::ArticulatedUnitPose> units;
    ch::rail_operation::ReturnPhase return_phase{};
    double radians=0.0;
    double time_s=0.0;
    int sequence=0;
    const char* label="";
    bool coupled=false;
};
[[nodiscard]] bool build_scene(RailPersistentState& state,
    ch::rail_live_operation::LiveOperationController& service,
    RailPlacementPieceId& turntable_group) {
    RailPlacementGraph graph;
    const auto root=graph.add_root({0,0,0},0);
    if(!root)return false;
    const auto approach=graph.append_straight(*root,40);
    if(!approach)return false;
    const auto station_a=graph.append_straight(approach->node,8);
    if(!station_a)return false;
    const auto rear=graph.append_turnout(station_a->node,96,.2617993878F,RailTurnDirection::left);
    if(!rear)return false;
    const auto far_root=graph.add_root({240,0,0},PI);
    if(!far_root)return false;
    const auto front=graph.append_turnout(*far_root,96,.2617993878F,RailTurnDirection::right);
    if(!front)return false;
    RailPlacementController editor(graph);
    if(!editor.begin(rear->through_node,RailPlacementMode::straight))return false;
    const auto main=editor.preview(
        graph.nodes()[front->through_node].position.x-
        graph.nodes()[rear->through_node].position.x);
    if(!main || !editor.commit() ||
       !graph.append_smooth_connector(rear->diverging_node,front->diverging_node))return false;
    state.nodes=graph.nodes();
    state.edges=graph.edges();
    turntable_group=graph.edges()[approach->edge].piece_group;
    state.stations={{graph.edges()[station_a->edge].piece_group,.25},
                    {graph.edges()[main->primary_edge].piece_group,.5}};
    state.turntables={{turntable_group,3500,2275}};
    std::unordered_set<RailPlacementPieceId> groups;
    for(const auto& edge:state.edges)if(groups.insert(edge.piece_group).second)
        state.actions.push_back({edge.piece_group,1250,812,true});
    return ch::rail_persistence::validate(state) &&
           service.sync_from_persistent_state(state) &&
           service.turntable_return_available();
}
[[nodiscard]] ch::CameraState follow(const Frame& frame) {
    ch::CameraState camera{};
    // Review capture: frame the complete return consist and avoid aggressive
    // locomotive-locked zoom that clips 5+ of 7 coaches from the screen.
    // Gameplay zoom remains player-controlled and is untouched.
    camera.zoom=0.26F; // Must match the SDL draw camera exactly.
    camera.rotation=ch::CameraRotation::r0;
    const auto& locomotive=frame.units.front().pose;
    // Lock view to a locomotive, but keep the detached station-B consist in
    // background for actual pass-by verification.
    float x=static_cast<float>(locomotive.x),y=static_cast<float>(locomotive.y);
    if(frame.sequence==3 && frame.units.size()==8U){
        // During the return, centre on the WHOLE locomotive-plus-seven
        // consist. Keeping the camera locked to the engine sent the last
        // wagons beyond the right viewport edge and triggered black SDL
        // software clipping artifacts in the review capture.
        const auto& tail=frame.units.back().pose;
        x=0.5F*(x+static_cast<float>(tail.x));
        y=0.5F*(y+static_cast<float>(tail.y));
    }
    // Project through the actual production camera contract. Hard-coded
    // 64/32 multipliers may diverge from the engine's tile scale and rotate
    // unexpectedly, forcing the turntable outside the recorded viewport.
    const auto projected=ch::world_to_screen_point(
        x,y,camera,static_cast<float>(W),static_cast<float>(H));
    camera.pan_x=static_cast<float>(W)*0.5F-projected.x;
    camera.pan_y=static_cast<float>(H)*0.5F-projected.y;
    return camera;
}
void draw_tracks(SDL_Renderer* renderer,const RailPersistentState& state,
                 const ch::CameraState& camera) {
    for(const auto& edge:state.edges) {
        if(!edge.active)continue;
        constexpr int steps=96;
        for(int rail=-1;rail<=1;rail+=2) {
            std::array<SDL_FPoint,steps+1> path{};
            for(int i=0;i<=steps;++i) {
                const auto pt=RailMeshBuilder::sample_cubic(edge.segment,
                    static_cast<float>(i)/steps);
                const auto t=RailMeshBuilder::sample_cubic(edge.segment,
                    std::min(1.F,(static_cast<float>(i)+.12F)/steps));
                const float dx=t.x-pt.x,dy=t.y-pt.y;
                const float norm=std::max(.0001F,std::hypot(dx,dy));
                const auto screen=ch::world_to_screen_point(
                    pt.x+(rail*.38F)*(-dy/norm),pt.y+(rail*.38F)*(dx/norm),pt.z+.02F,
                    camera,static_cast<float>(W),static_cast<float>(H));
                path[i]={screen.x,screen.y};
            }
            SDL_SetRenderDrawColor(renderer,93,75,49,255);
            SDL_RenderLines(renderer,path.data(),static_cast<int>(path.size()));
        }
    }
}
[[nodiscard]] int main_impl(const std::filesystem::path& out) {
    RailPersistentState state;
    ch::rail_live_operation::LiveOperationController service;
    RailPlacementPieceId table=kInvalidRailPlacementPieceId;
    if(!build_scene(state,service,table)){
        std::cerr<<"Rail screenshot fixture cannot compile the built track\n";
        return 2;
    }
    // Continuous physical timeline, not a montage assembled from four
    // unrelated clips. One output frame is one consecutive 0.5s update;
    // no phase resampling, time reversal, teleports or omitted couplings.
    constexpr double kSimulationSecondsPerFrame=0.5;
    constexpr int kMaxFrames=1200;
    std::vector<Frame> frames;
    frames.reserve(600);
    std::array<bool,6> saw_phase{};
    bool shunt_seen=false,coach_held=false,rotation_seen=false;
    bool recouple_seen=false,arrived_a=false;
    int parked_tail_frames=0;
    double previous_time=-1.0;
    std::optional<std::array<std::pair<double,double>,7>> parked_coaches;
    for(int tick=0;tick<kMaxFrames;++tick) {
        service.update(kSimulationSecondsPerFrame);
        auto units=service.articulated_poses();
        if(units.size()!=8U){
            std::cerr<<"SDL scene lost a vehicle\n";return 3;
        }
        const auto pose=service.train_pose();
        if(!pose)return 3;
        if(!std::isfinite(pose->x)||!std::isfinite(pose->y))return 3;
        int stage=0;
        const char* name="A TO B / TRAIN APPROACH";
        if(service.return_service_active()){
            const auto p=service.return_phase();
            if(p==ch::rail_operation::ReturnPhase::approach_turntable){
                stage=2;name="DETACHED / APPROACH TURNING DECK";
            } else if(p==ch::rail_operation::ReturnPhase::rotate_180){
                stage=3;name="LOCOMOTIVE STOPS / ROTATE 180";
            } else if(p==ch::rail_operation::ReturnPhase::reverse_to_coach){
                stage=4;name="TURN COMPLETE / MOVE TO COACHES";
            } else if(p==ch::rail_operation::ReturnPhase::coupled_return){
                stage=5;name="RECOUPLED / RETURN TO STATION A";
            } else if(p==ch::rail_operation::ReturnPhase::parked_at_a){
                stage=5;name="ARRIVED AT STATION A";
                arrived_a=true;
            }
        } else if(service.shunting_locomotive()){
            stage=1;name="STATION B / LOCOMOTIVE RUN-AROUND";
            shunt_seen=true;
        }
        saw_phase[stage]=true;
        if(service.shunting_locomotive()){
            std::array<std::pair<double,double>,7> positions{};
            for(std::size_t i=1;i<units.size();++i)
                positions[i-1]={units[i].pose.x,units[i].pose.y};
            if(!parked_coaches)parked_coaches=positions;
            else for(std::size_t i=0;i<7;++i)
                if(std::hypot(positions[i].first-(*parked_coaches)[i].first,
                              positions[i].second-(*parked_coaches)[i].second)>0.03){
                    std::cerr<<"Detached coach moved while locomotive shunted\n";return 4;
                }
            coach_held=true;
        }
        const double turn=service.turntable_rotation_radians();
        if(stage==3){
            rotation_seen=true;
            if(service.return_coupled())return 4;
        }
        if(service.return_coupled())recouple_seen=true;
        const double time=(tick+1)*kSimulationSecondsPerFrame;
        if(time<=previous_time)return 4;
        previous_time=time;
        frames.push_back({std::move(units),service.return_phase(),
            turn,time,stage,name,service.return_coupled()});
        if(arrived_a && ++parked_tail_frames>=8)break;
    }
    if(!arrived_a||!shunt_seen||!coach_held||!rotation_seen||
       !recouple_seen||!std::all_of(saw_phase.begin(),saw_phase.end(),
                                    [](bool flag){return flag;})){
        std::cerr<<"Continuous rail cycle incomplete; refusing montage\n";return 4;
    }
    if(frames.size()<60U || frames.size()>static_cast<std::size_t>(kMaxFrames))
        return 4;
    SDL_SetHint(SDL_HINT_RENDER_DRIVER,"software");
    if(!SDL_Init(SDL_INIT_VIDEO)){std::cerr<<SDL_GetError()<<'\n';return 5;}
    SDL_Window* window=SDL_CreateWindow("City Horizon / SDL Railway Review",W,H,
        SDL_WINDOW_HIDDEN);
    SDL_Renderer* renderer=window?SDL_CreateRenderer(window,nullptr):nullptr;
    if(!renderer){std::cerr<<SDL_GetError()<<'\n';return 6;}
    std::map<std::string,SDL_Texture*> textures;
    auto texture_provider=[&](const std::filesystem::path& file)->SDL_Texture* {
        const auto name=file.string();
        if(auto it=textures.find(name);it!=textures.end())return it->second;
        SDL_Surface* image=SDL_LoadPNG(name.c_str());
        if(!image){std::cerr<<"Missing approved PNG: "<<name<<'\n';return nullptr;}
        SDL_Texture* texture=SDL_CreateTextureFromSurface(renderer,image);
        SDL_DestroySurface(image);
        if(texture)SDL_SetTextureBlendMode(texture,SDL_BLENDMODE_BLEND);
        textures.emplace(name,texture);
        return texture;
    };
    std::filesystem::create_directories(out);
    int index=0;
    // The camera follows the ACTUAL service at a constant preview zoom.
    // Its target is smoothly filtered; no abrupt editorial camera resets.
    ch::CameraState camera{};
    camera.zoom=0.26F;
    camera.rotation=ch::CameraRotation::r0;
    double previous_loco_x=std::numeric_limits<double>::quiet_NaN();
    double previous_loco_y=std::numeric_limits<double>::quiet_NaN();
    double previous_angle=0.0;
    std::ofstream chronology(out/"chronology.csv");
    chronology<<"frame,simulation_seconds,phase,coupled,locomotive_x,locomotive_y,turn_radians\n";
    for(const Frame& frame:frames){
        const auto& locomotive=frame.units.front().pose;
        if(std::isfinite(previous_loco_x)){
            // 3.25m/s at 0.5s per frame, plus a tolerance for short
            // state-machine transitions; teleporting invalidates the proof.
            const double distance=std::hypot(locomotive.x-previous_loco_x,
                                              locomotive.y-previous_loco_y);
            if(distance>4.25){
                std::cerr<<"Rail visual discontinuity at "<<frame.time_s
                         <<" seconds: "<<distance<<"m\n";
                return 11;
            }
        }
        if(frame.radians+0.0001<previous_angle)return 11;
        previous_angle=frame.radians;
        previous_loco_x=locomotive.x;
        previous_loco_y=locomotive.y;
        chronology<<index<<","<<frame.time_s<<","<<frame.sequence<<","
                  <<frame.coupled<<","<<locomotive.x<<","
                  <<locomotive.y<<","<<frame.radians<<"\n";
        const auto target=follow(frame);
        if(index==0){camera.pan_x=target.pan_x;camera.pan_y=target.pan_y;}
        else {
            const float kFollow=0.17F;
            camera.pan_x+=(target.pan_x-camera.pan_x)*kFollow;
            camera.pan_y+=(target.pan_y-camera.pan_y)*kFollow;
        }
        SDL_SetRenderDrawBlendMode(renderer,SDL_BLENDMODE_BLEND);
        SDL_SetRenderDrawColor(renderer,72,105,90,255);
        SDL_RenderClear(renderer);
        draw_tracks(renderer,state,camera);
        for(const auto& edge:state.edges){
            if(!edge.active || edge.piece_group!=table)continue;
            if(!ch::rail_turntable_visual::render(renderer,edge,frame.radians,
                   camera,static_cast<float>(W),static_cast<float>(H))){
                std::cerr<<"Turntable sprite renderer rejected approved asset\n";
                return 7;
            }
            break;
        }
        std::vector<const ch::rail_operation::ArticulatedUnitPose*> sorted;
        for(const auto& unit:frame.units)sorted.push_back(&unit);
        std::stable_sort(sorted.begin(),sorted.end(),[&](auto* a,auto* b){
            return ch::camera_depth_key(static_cast<float>(a->pose.x),
                        static_cast<float>(a->pose.y),camera) <
                   ch::camera_depth_key(static_cast<float>(b->pose.x),
                        static_cast<float>(b->pose.y),camera);
        });
        for(const auto* unit:sorted)
            ch::rail_train_visual::render_unit(renderer,*unit,camera,
                static_cast<float>(W),static_cast<float>(H),texture_provider);
        SDL_FRect caption_background{0.0F,0.0F,static_cast<float>(W),52.0F};
        SDL_SetRenderDrawColor(renderer,14,22,24,220);
        SDL_RenderFillRect(renderer,&caption_background);
        SDL_SetRenderDrawColor(renderer,255,241,200,255);
        SDL_RenderDebugText(renderer,16.0F,10.0F,
                            "CITY HORIZON / CONTINUOUS SDL RAIL CYCLE");
        SDL_RenderDebugText(renderer,16.0F,29.0F,frame.label);
        SDL_RenderPresent(renderer);
        SDL_Surface* pixels=SDL_RenderReadPixels(renderer,nullptr);
        if(!pixels){std::cerr<<"SDL_RenderReadPixels: "<<SDL_GetError()<<'\n';return 8;}
        std::ostringstream fname;
        fname<<"frame_"<<std::setw(4)<<std::setfill('0')<<index++<<".png";
        const bool wrote=SDL_SavePNG(pixels,(out/fname.str()).string().c_str());
        SDL_DestroySurface(pixels);
        if(!wrote){std::cerr<<"SDL_SavePNG: "<<SDL_GetError()<<'\n';return 9;}
    }
    chronology.close();
    for(auto& [name,texture]:textures)if(texture)SDL_DestroyTexture(texture);
    SDL_DestroyRenderer(renderer);
    SDL_DestroyWindow(window);
    SDL_Quit();
    if(index!=static_cast<int>(frames.size()))return 10;
    std::cout<<"CH_RAIL_SDL_CONTINUOUS_CAPTURE_V2 PASS: "<<index
             <<" contiguous frames, complete A to B to A operation, "
             <<"real 8-unit controller, no simulated teleports, SDL pixels\n";
    return 0;
}
}
int main(int argc,char** argv) {
    if(argc!=2){std::cerr<<"usage: rail_sdl_render_capture <output_dir>\n";return 1;}
    return main_impl(argv[1]);
}
