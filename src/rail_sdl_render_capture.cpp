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
    camera.zoom=(frame.sequence==3)?0.27F:0.36F;
    camera.rotation=ch::CameraRotation::r0;
    const auto& locomotive=frame.units.front().pose;
    // Lock view to a locomotive, but keep the detached station-B consist in
    // background for actual pass-by verification.
    const float x=static_cast<float>(locomotive.x),y=static_cast<float>(locomotive.y);
    camera.pan_x=-(x-y)*64.0F*camera.zoom;
    camera.pan_y=-(x+y)*32.0F*camera.zoom;
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
    std::array<std::vector<Frame>,4> phases;
    const char* phase_names[]={"LOCOMOTIVE_ON_SIDING","APPROACH_TURNTABLE",
                               "ROTATION_180","COUPLED_RETURN"};
    bool saw_siding=false,saw_approach=false,saw_rotation=false,saw_return=false;
    for(int tick=0;tick<8000;++tick) {
        service.update(.1);
        int stage=-1;
        if(service.return_service_active()){
            const auto p=service.return_phase();
            if(p==ch::rail_operation::ReturnPhase::approach_turntable)stage=1;
            if(p==ch::rail_operation::ReturnPhase::rotate_180)stage=2;
            if(p==ch::rail_operation::ReturnPhase::coupled_return)stage=3;
        } else if(service.shunting_locomotive() &&
                  service.locomotive_shunt_phase() ==
                    ch::rail_operation::DetachedShuntPhase::bypass_reverse)stage=0;
        if(stage<0)continue;
        if(tick%5!=0)continue;
        auto units=service.articulated_poses();
        if(units.size()!=8U){
            std::cerr<<"SDL scene lost a vehicle\n";return 3;
        }
        phases[stage].push_back({std::move(units),service.return_phase(),
            service.turntable_rotation_radians(),tick*.1,stage,phase_names[stage]});
        if(stage==0)saw_siding=true;
        if(stage==1)saw_approach=true;
        if(stage==2)saw_rotation=true;
        if(stage==3)saw_return=true;
    }
    if(!saw_siding||!saw_approach||!saw_rotation||!saw_return){
        std::cerr<<"Missing physical scene stage\n";return 4;
    }
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
    std::array<int,4> emitted{};
    for(int stage=0;stage<4;++stage){
        const auto& frames=phases[stage];
        if(frames.empty())continue;
        constexpr int frames_per_phase=24;
        for(int n=0;n<frames_per_phase;++n){
            const Frame& frame=frames[std::min(frames.size()-1,
               (frames.size()-1)*static_cast<std::size_t>(n)/(frames_per_phase-1))];
            const auto camera=follow(frame);
            SDL_SetRenderDrawBlendMode(renderer,SDL_BLENDMODE_BLEND);
            SDL_SetRenderDrawColor(renderer,72,105,90,255);
            SDL_RenderClear(renderer);
            draw_tracks(renderer,state,camera);
            // Render the same Blender 104-image compositor as the interactive
            // game, and check every chosen asset has a valid render path.
            for(const auto& edge:state.edges){
                if(!edge.active || edge.piece_group!=table)continue;
                const double angle=stage==2?frame.radians:
                    stage==3?static_cast<double>(PI):0.0;
                if(!ch::rail_turntable_visual::render(renderer,edge,angle,
                       camera,static_cast<float>(W),static_cast<float>(H))){
                    std::cerr<<"Turntable sprite renderer rejected approved asset\n";return 7;
                }
                break;
            }
            // Independent locomotive and 7 coached poses, identical production
            // renderer, world depth and 8-view sprites (no synthetic chassis).
            std::vector<const ch::rail_operation::ArticulatedUnitPose*> sorted;
            for(const auto& unit:frame.units)sorted.push_back(&unit);
            std::stable_sort(sorted.begin(),sorted.end(),[](auto* a,auto* b){
                return a->pose.x+a->pose.y<b->pose.x+b->pose.y;
            });
            for(const auto* unit:sorted)
                ch::rail_train_visual::render_unit(renderer,*unit,camera,
                    static_cast<float>(W),static_cast<float>(H),texture_provider);
            // Explicit slate for every editorial cut: selected operational
            // stages are *not* adjacent simulation ticks. The captured clip
            // must not falsely imply a train teleported between locations.
            SDL_FRect caption_background{0.0F,0.0F,static_cast<float>(W),52.0F};
            SDL_SetRenderDrawColor(renderer,14,22,24,220);
            SDL_RenderFillRect(renderer,&caption_background);
            SDL_SetRenderDrawColor(renderer,255,241,200,255);
            SDL_RenderDebugText(renderer,16.0F,10.0F,
                                "CITY HORIZON / RAIL SDL VISUAL VALIDATION");
            SDL_RenderDebugText(renderer,16.0F,29.0F,frame.label);
            // Show a visible cut to mark the four selected chronological
            // chapters; the game itself never makes these editor jump cuts.
            if(n<3 || n>20) {
                const int edge=std::min(n,23-n);
                const Uint8 opacity=static_cast<Uint8>((3-edge)*65);
                SDL_SetRenderDrawColor(renderer,0,0,0,opacity);
                SDL_RenderFillRect(renderer,nullptr);
            }
            SDL_RenderPresent(renderer);
            SDL_Surface* pixels=SDL_RenderReadPixels(renderer,nullptr);
            if(!pixels){std::cerr<<"SDL_RenderReadPixels: "<<SDL_GetError()<<'\n';return 8;}
            std::ostringstream fname;
            fname<<"frame_"<<std::setw(4)<<std::setfill('0')<<index++<<".png";
            const auto path=out/fname.str();
            const bool wrote=SDL_SavePNG(pixels,path.string().c_str());
            SDL_DestroySurface(pixels);
            if(!wrote){std::cerr<<"SDL_SavePNG: "<<SDL_GetError()<<'\n';return 9;}
            ++emitted[stage];
        }
    }
    for(auto& [name,texture]:textures)if(texture)SDL_DestroyTexture(texture);
    SDL_DestroyRenderer(renderer);
    SDL_DestroyWindow(window);
    SDL_Quit();
    if(index!=96)return 10;
    std::cout<<"CH_RAIL_SDL_RENDER_CAPTURE_V1 PASS: "<<index
             <<" frames, four operational phases, actual CH Blender sprites, "
             <<"real 8-unit controller, SDL pixels\n";
    return 0;
}
}
int main(int argc,char** argv) {
    if(argc!=2){std::cerr<<"usage: rail_sdl_render_capture <output_dir>\n";return 1;}
    return main_impl(argv[1]);
}
