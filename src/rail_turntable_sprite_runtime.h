#pragma once
// CH_RAIL_TURNTABLE_SPRITE_RUNTIME_V1
// Approved CH_CAMERA_V1 sprite layers: fixed Blender pit + 25 angle samples
// of the moving bridge. Never rotate 2D pixels to fake an isometric 3D turn.
// Generic non-cardinal track headings retain the current procedural fallback.
#include "rail_persistence.h"
#include "src/ch_core/projection.h"

#include <SDL3/SDL.h>
#include <algorithm>
#include <array>
#include <cmath>
#include <cstdio>
#include <filesystem>
#include <optional>
#include <string>

namespace ch::rail_turntable_visual {

inline constexpr int kLastFrame = 24;
inline constexpr float kPi = 3.14159265358979323846F;
// Same fixed CH Blender CH_CAMERA_V1 orthographic framing for all 4 views.
inline constexpr float kProxyTileWidthPx = 96.3081817627F;
inline constexpr float kProxyOriginXPx = 128.00001526F;
inline constexpr float kProxyOriginYPx = 152.57353973F;
inline constexpr float kBaseResolution = 1024.0F;
inline constexpr float kBridgeResolution = 512.0F;

enum class View { south, east, north, west };

[[nodiscard]] inline const char* view_label(View view) noexcept {
    switch(view) {
        case View::south:return "south";
        case View::east:return "east";
        case View::north:return "north";
        case View::west:return "west";
    }
    return "south";
}

// Strict cardinal gate: a texture asset has canonical views only, rather than
// claiming arbitrary straight orientations which the artist never rendered.
[[nodiscard]] inline std::optional<View> authored_view(
    float dx, float dy, const ch::CameraState& camera) noexcept {
    const auto relative = ch::camera_view_point(dx,dy,camera.rotation);
    const float norm=std::hypot(relative.x,relative.y);
    if(!(norm>0.00001F) || !std::isfinite(norm))return std::nullopt;
    const float x=relative.x/norm,y=relative.y/norm;
    constexpr float kCardinalTolerance=0.00873F; // half a degree
    if(std::abs(y)<kCardinalTolerance)
        return x>0?View::south:View::north;
    if(std::abs(x)<kCardinalTolerance)
        return y>0?View::east:View::west;
    return std::nullopt;
}

[[nodiscard]] inline int frame_index(double radians) noexcept {
    if(!std::isfinite(radians))return 0;
    return std::clamp(static_cast<int>(std::lround(
        std::clamp(radians,0.0,static_cast<double>(kPi))*
        kLastFrame/static_cast<double>(kPi))),0,kLastFrame);
}

[[nodiscard]] inline std::filesystem::path asset_path(View view,int phase,bool base) {
    const std::filesystem::path root="assets/rail/turntable_7m2_01";
    if(base)return root/(std::string("rail_turntable_base_")+view_label(view)+".png");
    char suffix[20];
    std::snprintf(suffix,sizeof(suffix),"_phase_%02d.png",
                  std::clamp(phase,0,kLastFrame));
    return root/(std::string("rail_turntable_bridge_")+view_label(view)+suffix);
}

[[nodiscard]] inline bool catalog_ready() {
    // The runtime must fail closed on a partial download; never show only
    // one layer (or draw duplicate procedural/baked bridge surfaces).
    static const bool ready=[](){
        const auto root=std::filesystem::path("assets/rail/turntable_7m2_01");
        if(!std::filesystem::is_regular_file(root/"runtime_manifest.json"))return false;
        for(View view:{View::south,View::east,View::north,View::west}) {
            if(!std::filesystem::is_regular_file(asset_path(view,0,true)))return false;
            for(int f=0;f<=kLastFrame;++f)
                if(!std::filesystem::is_regular_file(asset_path(view,f,false)))return false;
        }
        return true;
    }();
    return ready;
}

[[nodiscard]] inline SDL_Texture* get_texture(
    SDL_Renderer* renderer, const std::filesystem::path& file) {
    const SDL_PropertiesID props=SDL_GetRendererProperties(renderer);
    if(!props)return nullptr;
    const std::string key=std::string("ch.rail.turntable.")+file.filename().string();
    if(SDL_HasProperty(props,key.c_str()))
        return static_cast<SDL_Texture*>(
            SDL_GetPointerProperty(props,key.c_str(),nullptr));
    // Avoid retrying missing textures every frame.
    if(!std::filesystem::is_regular_file(file))return nullptr;
    SDL_Surface* surface=SDL_LoadPNG(file.string().c_str());
    if(!surface)return nullptr;
    SDL_Texture* texture=SDL_CreateTextureFromSurface(renderer,surface);
    SDL_DestroySurface(surface);
    if(!texture)return nullptr;
    (void)SDL_SetTextureBlendMode(texture,SDL_BLENDMODE_BLEND);
    if(!SDL_SetPointerPropertyWithCleanup(
       props,key.c_str(),texture,[](void*,void* ptr){
           SDL_DestroyTexture(static_cast<SDL_Texture*>(ptr));
       },nullptr)) {
        SDL_DestroyTexture(texture);
        return nullptr;
    }
    return texture;
}

// Same orthographic projection contract and ground pivot for BOTH PNG layers.
// Instead of hand-tuning at one zoom, calibrate using projected 3x3m tile width
// so the 7.2m diameter aligns with the physical track at all zoom values.
[[nodiscard]] inline std::optional<SDL_FRect> destination_rect(
    const ch::CameraState& camera, float viewport_w, float viewport_h,
    float world_x,float world_y,float world_z,float source_resolution) {
    const std::array<ch::WorldPoint3,4> corners{{
        {world_x-1.5F,world_y-1.5F,world_z},
        {world_x+1.5F,world_y-1.5F,world_z},
        {world_x+1.5F,world_y+1.5F,world_z},
        {world_x-1.5F,world_y+1.5F,world_z}
    }};
    float minx=1.0e9F,maxx=-1.0e9F;
    for(const auto& pt:corners) {
        const auto v=ch::world_to_screen_point(pt,camera,viewport_w,viewport_h);
        minx=std::min(minx,v.x);maxx=std::max(maxx,v.x);
    }
    const float tile_w=maxx-minx;
    const float baked_tile_w=kProxyTileWidthPx*(source_resolution/256.0F);
    if(!(tile_w>1.0F) || !(baked_tile_w>0.0F) ||
       !std::isfinite(tile_w) || !std::isfinite(baked_tile_w))
       return std::nullopt;
    const float scale=tile_w/baked_tile_w;
    const auto center=ch::world_to_screen_point(
        world_x,world_y,world_z,camera,viewport_w,viewport_h);
    const float origin_x=kProxyOriginXPx*(source_resolution/256.0F);
    const float origin_y=kProxyOriginYPx*(source_resolution/256.0F);
    const SDL_FRect dst{center.x-origin_x*scale,center.y-origin_y*scale,
                        source_resolution*scale,source_resolution*scale};
    return dst;
}

[[nodiscard]] inline bool render(
    SDL_Renderer* renderer,
    const RailPlacementEdge& edge,
    double rotation_radians,
    const ch::CameraState& camera,float viewport_w,float viewport_h) {
    if(!renderer || !catalog_ready() ||
       edge.kind!=RailPlacementEdgeKind::straight)return false;
    const float dx=edge.segment.end.x-edge.segment.start.x;
    const float dy=edge.segment.end.y-edge.segment.start.y;
    const auto view=authored_view(dx,dy,camera);
    if(!view)return false;
    const auto middle=RailMeshBuilder::sample_cubic(edge.segment,0.5F);
    // The 1024px transparent canvas occupies much more space than the
    // *physical* 7.2m circular deck. An offscreen platform must never submit
    // its enormous transparent quad to SDL's software renderer: on the rail
    // video runner its clipped RGBA backing appeared as an opaque black box.
    // Compute conservative extents from the actual world-space radius, not
    // from the image rectangle or the engine camera's cinematic zoom.
    float lo_x=1.0e9F,hi_x=-1.0e9F,lo_y=1.0e9F,hi_y=-1.0e9F;
    constexpr float radius_m=3.65F;
    for(const auto [ox,oy]:std::array<std::array<float,2>,8>{{
        {{-radius_m,-radius_m}},{{-radius_m,0}},{{-radius_m,radius_m}},
        {{0,-radius_m}},{{0,radius_m}},{{radius_m,-radius_m}},
        {{radius_m,0}},{{radius_m,radius_m}}
    }}) {
        const auto pixel=ch::world_to_screen_point(
            middle.x+ox,middle.y+oy,middle.z,camera,viewport_w,viewport_h);
        lo_x=std::min(lo_x,pixel.x);hi_x=std::max(hi_x,pixel.x);
        lo_y=std::min(lo_y,pixel.y);hi_y=std::max(hi_y,pixel.y);
    }
    if(hi_x<0.0F || hi_y<0.0F || lo_x>viewport_w || lo_y>viewport_h)
        return true; // successfully culled, neither layer drawn
    const auto base_dst=destination_rect(camera,viewport_w,viewport_h,
                           middle.x,middle.y,middle.z,kBaseResolution);
    const auto bridge_dst=destination_rect(camera,viewport_w,viewport_h,
                           middle.x,middle.y,middle.z,kBridgeResolution);
    if(!base_dst||!bridge_dst)return false;
    SDL_Texture* base=get_texture(renderer,asset_path(*view,0,true));
    SDL_Texture* bridge=get_texture(renderer,asset_path(*view,
                                            frame_index(rotation_radians),false));
    if(!base || !bridge)return false;
    // The software SDL review renderer can expose a black texture backing
    // for partially offscreen 512/1024 RGBA turntable layers. Clip both axes
    // in SOURCE and DESTINATION space before asking any SDL backend to draw.
    // The actual city runtime uses the same compositor, so this also guards
    // near-viewport construction during gameplay.
    auto draw_visible=[&](SDL_Texture* texture,const SDL_FRect& dst)->bool {
        if(!(dst.w>0.0F && dst.h>0.0F))return false;
        const float left=std::max(0.0F,dst.x);
        const float top=std::max(0.0F,dst.y);
        const float right=std::min(viewport_w,dst.x+dst.w);
        const float bottom=std::min(viewport_h,dst.y+dst.h);
        if(right<=left || bottom<=top)return true; // safely out of view
        float tw=0.0F,th=0.0F;
        if(!SDL_GetTextureSize(texture,&tw,&th) || tw<=0 || th<=0)return false;
        const SDL_FRect visible{left,top,right-left,bottom-top};
        const SDL_FRect source{
            (left-dst.x)*tw/dst.w,(top-dst.y)*th/dst.h,
            visible.w*tw/dst.w,visible.h*th/dst.h};
        return SDL_RenderTexture(renderer,texture,&source,&visible);
    };
    if(!draw_visible(base,*base_dst))return false;
    return draw_visible(bridge,*bridge_dst);
}

} // namespace ch::rail_turntable_visual
