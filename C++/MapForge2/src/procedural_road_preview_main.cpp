#include <QBackingStore>
#include <QColor>
#include <QExposeEvent>
#include <QGuiApplication>
#include <QImage>
#include <QKeyEvent>
#include <QMouseEvent>
#include <QPainter>
#include <QPainterPath>
#include <QPen>
#include <QPointF>
#include <QPolygonF>
#include <QRegion>
#include <QResizeEvent>
#include <QString>
#include <QWheelEvent>
#include <QWindow>

#include <algorithm>
#include <array>
#include <cmath>
#include <filesystem>
#include <iostream>

#include "src/ch_core/projection.h"
#include "src/road_system.h"

namespace {

constexpr int kPreviewWidth = 1280;
constexpr int kPreviewHeight = 720;

QPointF to_qpoint(const ch::ScreenPoint point) {
    return {static_cast<qreal>(point.x), static_cast<qreal>(point.y)};
}

RoadSplineSegment default_segment() {
    RoadSplineSegment segment;
    segment.start = {-5.0F, 0.0F, 0.0F};
    segment.control_a = {-1.0F, 3.4F, 0.0F};
    segment.control_b = {4.5F, -3.4F, 1.15F};
    segment.end = {9.0F, 0.0F, 1.35F};
    segment.width = 0.78F;
    segment.texture_repeat_world_units = 1.0F;
    segment.subdivisions = 64;
    return segment;
}

ch::CameraState default_camera() {
    ch::CameraState camera;
    camera.zoom = 0.76F;
    camera.pan_x = -70.0F;
    camera.pan_y = -15.0F;
    return camera;
}

const RoadWorldPoint3& handle_point(const RoadSplineSegment& segment, const int index) {
    switch (index) {
        case 0: return segment.start;
        case 1: return segment.control_a;
        case 2: return segment.control_b;
        case 3: return segment.end;
        default: return segment.start;
    }
}

RoadWorldPoint3* editable_handle(RoadSplineSegment& segment, const int index) {
    switch (index) {
        case 0: return &segment.start;
        case 1: return &segment.control_a;
        case 2: return &segment.control_b;
        case 3: return &segment.end;
        default: return nullptr;
    }
}

void draw_ground(QPainter& painter, const ch::CameraState& camera,
                 const float viewport_width, const float viewport_height) {
    const QColor grass_a(101, 137, 92);
    const QColor grass_b(96, 131, 88);
    QPen edge_pen(QColor(76, 105, 72, 150));
    edge_pen.setWidthF(0.8);
    painter.setPen(edge_pen);

    for (int y = -10; y <= 10; ++y) {
        for (int x = -12; x <= 17; ++x) {
            QPolygonF diamond;
            diamond << to_qpoint(ch::world_to_screen_point(static_cast<float>(x), static_cast<float>(y), camera,
                                                           viewport_width, viewport_height))
                    << to_qpoint(ch::world_to_screen_point(static_cast<float>(x + 1), static_cast<float>(y), camera,
                                                           viewport_width, viewport_height))
                    << to_qpoint(ch::world_to_screen_point(static_cast<float>(x + 1), static_cast<float>(y + 1), camera,
                                                           viewport_width, viewport_height))
                    << to_qpoint(ch::world_to_screen_point(static_cast<float>(x), static_cast<float>(y + 1), camera,
                                                           viewport_width, viewport_height));
            painter.setBrush(((x + y) & 1) == 0 ? grass_a : grass_b);
            painter.drawPolygon(diamond);
        }
    }
}

void draw_support(QPainter& painter, const RoadWorldPoint3& point, const ch::CameraState& camera,
                  const float viewport_width, const float viewport_height) {
    if (point.z <= 0.12F) return;
    const ch::ScreenPoint top = ch::world_to_screen_point(point.x, point.y, point.z, camera,
                                                          viewport_width, viewport_height);
    const ch::ScreenPoint bottom = ch::world_to_screen_point(point.x, point.y, 0.0F, camera,
                                                             viewport_width, viewport_height);
    QPen shadow(QColor(45, 49, 52, 105));
    shadow.setWidthF(12.0);
    shadow.setCapStyle(Qt::FlatCap);
    painter.setPen(shadow);
    painter.drawLine(to_qpoint(top), to_qpoint(bottom));

    QPen pillar(QColor(122, 126, 126));
    pillar.setWidthF(7.0);
    pillar.setCapStyle(Qt::FlatCap);
    painter.setPen(pillar);
    painter.drawLine(to_qpoint(top), to_qpoint(bottom));
}

void draw_mesh(QPainter& painter, const RoadMesh& mesh, const ch::CameraState& camera,
               const float viewport_width, const float viewport_height) {
    if (mesh.empty()) return;
    painter.setBrush(QColor(52, 57, 60));
    QPen edge_pen(QColor(34, 38, 40));
    edge_pen.setWidthF(0.8);
    painter.setPen(edge_pen);

    for (std::size_t index = 0; index + 2 < mesh.indices.size(); index += 3) {
        QPolygonF triangle;
        for (int corner = 0; corner < 3; ++corner) {
            const RoadMeshVertex& vertex = mesh.vertices[mesh.indices[index + static_cast<std::size_t>(corner)]];
            triangle << to_qpoint(ch::world_to_screen_point(
                vertex.position.x, vertex.position.y, vertex.position.z,
                camera, viewport_width, viewport_height));
        }
        painter.drawPolygon(triangle);
    }
}

void draw_centerline(QPainter& painter, const RoadSplineSegment& segment, const ch::CameraState& camera,
                     const float viewport_width, const float viewport_height) {
    QPainterPath path;
    constexpr int kSamples = 96;
    for (int index = 0; index <= kSamples; ++index) {
        const float t = static_cast<float>(index) / static_cast<float>(kSamples);
        const RoadWorldPoint3 point = RoadMeshBuilder::sample_cubic(segment, t);
        const QPointF screen = to_qpoint(ch::world_to_screen_point(
            point.x, point.y, point.z + 0.012F,
            camera, viewport_width, viewport_height));
        if (index == 0) path.moveTo(screen);
        else path.lineTo(screen);
    }
    QPen lane_pen(QColor(235, 220, 157, 220));
    lane_pen.setWidthF(2.0);
    lane_pen.setStyle(Qt::DashLine);
    painter.setPen(lane_pen);
    painter.setBrush(Qt::NoBrush);
    painter.drawPath(path);
}

void draw_handles(QPainter& painter, const RoadSplineSegment& segment, const ch::CameraState& camera,
                  const int selected_handle, const float viewport_width, const float viewport_height) {
    const auto screen_for = [&](const int index) {
        const RoadWorldPoint3& p = handle_point(segment, index);
        return to_qpoint(ch::world_to_screen_point(p.x, p.y, p.z, camera, viewport_width, viewport_height));
    };

    QPen guide(QColor(93, 208, 232, 175));
    guide.setWidthF(1.5);
    guide.setStyle(Qt::DashLine);
    painter.setPen(guide);
    painter.setBrush(Qt::NoBrush);
    painter.drawLine(screen_for(0), screen_for(1));
    painter.drawLine(screen_for(2), screen_for(3));

    for (int index = 0; index < 4; ++index) {
        const QPointF p = screen_for(index);
        const bool selected = index == selected_handle;
        painter.setPen(QPen(selected ? QColor(255, 230, 92) : QColor(222, 241, 245), selected ? 3.0 : 2.0));
        painter.setBrush(selected ? QColor(255, 174, 58) : QColor(35, 129, 160));
        painter.drawEllipse(p, selected ? 8.0 : 6.0, selected ? 8.0 : 6.0);

        const RoadWorldPoint3& world = handle_point(segment, index);
        painter.setPen(QPen(QColor(245, 249, 250), 1.0));
        painter.drawText(p + QPointF(10.0, -8.0),
                         QString("%1  z=%2").arg(index).arg(world.z, 0, 'f', 2));
    }
}

void draw_overlay(QPainter& painter, const RoadSplineSegment& segment, const int selected_handle,
                  const int viewport_width, const int viewport_height) {
    painter.setPen(Qt::NoPen);
    painter.setBrush(QColor(24, 30, 33, 205));
    painter.drawRoundedRect(QRectF(18.0, 18.0, 455.0, 92.0), 8.0, 8.0);
    painter.setPen(QColor(235, 242, 244));
    painter.drawText(QPointF(34.0, 43.0), "CH_PROCEDURAL_ROAD_MESH_V1 — interactive MapForge pilot");
    painter.drawText(QPointF(34.0, 65.0), "Drag handles: XY  |  PageUp/PageDown: Z  |  1-4: camera rotation");
    painter.drawText(QPointF(34.0, 87.0), "R: reset  |  RMB/MMB: pan  |  wheel: zoom  |  Esc: deselect");

    if (selected_handle >= 0) {
        const RoadWorldPoint3& p = handle_point(segment, selected_handle);
        painter.drawText(QPointF(34.0, static_cast<qreal>(viewport_height - 24)),
                         QString("Selected handle %1 — world (%2, %3, %4), width %5")
                             .arg(selected_handle)
                             .arg(p.x, 0, 'f', 2).arg(p.y, 0, 'f', 2).arg(p.z, 0, 'f', 2)
                             .arg(segment.width, 0, 'f', 2));
    }
    (void)viewport_width;
}

void render_scene(QPainter& painter, const RoadSplineSegment& segment, const ch::CameraState& camera,
                  const int selected_handle, const int viewport_width, const int viewport_height) {
    painter.setRenderHint(QPainter::Antialiasing, true);
    painter.fillRect(QRect(0, 0, viewport_width, viewport_height), QColor(71, 96, 76));
    const float width = static_cast<float>(viewport_width);
    const float height = static_cast<float>(viewport_height);

    draw_ground(painter, camera, width, height);
    for (const float t : {0.25F, 0.50F, 0.75F}) {
        draw_support(painter, RoadMeshBuilder::sample_cubic(segment, t), camera, width, height);
    }
    draw_mesh(painter, RoadMeshBuilder::build_cubic(segment), camera, width, height);
    draw_centerline(painter, segment, camera, width, height);
    draw_handles(painter, segment, camera, selected_handle, width, height);
    draw_overlay(painter, segment, selected_handle, viewport_width, viewport_height);
}

bool render_png(const std::filesystem::path& output) {
    QImage image(kPreviewWidth, kPreviewHeight, QImage::Format_ARGB32_Premultiplied);
    QPainter painter(&image);
    render_scene(painter, default_segment(), default_camera(), -1, kPreviewWidth, kPreviewHeight);
    painter.end();

    const std::filesystem::path parent = output.parent_path();
    if (!parent.empty()) std::filesystem::create_directories(parent);
    return image.save(QString::fromStdString(output.string()), "PNG");
}

class RoadPilotWindow final : public QWindow {
public:
    RoadPilotWindow()
        : backing_store_(this), segment_(default_segment()), camera_(default_camera()) {
        setTitle(QStringLiteral("City Horizon — Procedural Road Pilot"));
        resize(kPreviewWidth, kPreviewHeight);
    }

protected:
    void exposeEvent(QExposeEvent*) override {
        if (isExposed()) render_now();
    }

    void resizeEvent(QResizeEvent* event) override {
        backing_store_.resize(event->size());
        if (isExposed()) render_now();
    }

    void mousePressEvent(QMouseEvent* event) override {
        if (event->button() == Qt::LeftButton) {
            selected_handle_ = hit_test(event->position());
            dragging_handle_ = selected_handle_ >= 0;
            render_now();
            return;
        }
        if (event->button() == Qt::RightButton || event->button() == Qt::MiddleButton) {
            panning_ = true;
            last_pointer_ = event->position();
        }
    }

    void mouseMoveEvent(QMouseEvent* event) override {
        if (dragging_handle_ && selected_handle_ >= 0) {
            RoadWorldPoint3* handle = editable_handle(segment_, selected_handle_);
            if (handle != nullptr) {
                const ch::WorldPoint world = ch::screen_to_world_point(
                    static_cast<float>(event->position().x()), static_cast<float>(event->position().y()),
                    camera_, static_cast<float>(width()), static_cast<float>(height()));
                handle->x = world.x;
                handle->y = world.y;
                render_now();
            }
            return;
        }
        if (panning_) {
            const QPointF delta = event->position() - last_pointer_;
            camera_.pan_x += static_cast<float>(delta.x());
            camera_.pan_y += static_cast<float>(delta.y());
            last_pointer_ = event->position();
            render_now();
        }
    }

    void mouseReleaseEvent(QMouseEvent* event) override {
        if (event->button() == Qt::LeftButton) dragging_handle_ = false;
        if (event->button() == Qt::RightButton || event->button() == Qt::MiddleButton) panning_ = false;
    }

    void wheelEvent(QWheelEvent* event) override {
        const float factor = event->angleDelta().y() > 0 ? 1.12F : (1.0F / 1.12F);
        camera_.zoom = std::clamp(camera_.zoom * factor, 0.30F, 3.0F);
        render_now();
    }

    void keyPressEvent(QKeyEvent* event) override {
        if (event->key() == Qt::Key_Escape) {
            selected_handle_ = -1;
            dragging_handle_ = false;
            render_now();
            return;
        }
        if (event->key() == Qt::Key_R) {
            segment_ = default_segment();
            camera_ = default_camera();
            selected_handle_ = -1;
            render_now();
            return;
        }
        if (event->key() >= Qt::Key_1 && event->key() <= Qt::Key_4) {
            camera_.rotation = static_cast<ch::CameraRotation>(event->key() - Qt::Key_1);
            render_now();
            return;
        }
        if ((event->key() == Qt::Key_PageUp || event->key() == Qt::Key_PageDown) && selected_handle_ >= 0) {
            RoadWorldPoint3* handle = editable_handle(segment_, selected_handle_);
            if (handle != nullptr) {
                const float step = (event->modifiers() & Qt::ShiftModifier) ? 0.25F : 0.10F;
                const float delta = event->key() == Qt::Key_PageUp ? step : -step;
                handle->z = std::clamp(handle->z + delta, 0.0F, 8.0F);
                render_now();
            }
            return;
        }
        QWindow::keyPressEvent(event);
    }

private:
    int hit_test(const QPointF& point) const {
        constexpr double radius = 15.0;
        constexpr double radius_sq = radius * radius;
        for (int index = 0; index < 4; ++index) {
            const RoadWorldPoint3& handle = handle_point(segment_, index);
            const ch::ScreenPoint screen = ch::world_to_screen_point(
                handle.x, handle.y, handle.z, camera_, static_cast<float>(width()), static_cast<float>(height()));
            const double dx = point.x() - static_cast<double>(screen.x);
            const double dy = point.y() - static_cast<double>(screen.y);
            if (dx * dx + dy * dy <= radius_sq) return index;
        }
        return -1;
    }

    void render_now() {
        if (!isExposed()) return;
        backing_store_.resize(size());
        const QRegion region(QRect(QPoint(0, 0), size()));
        backing_store_.beginPaint(region);
        if (QPaintDevice* device = backing_store_.paintDevice()) {
            QPainter painter(device);
            render_scene(painter, segment_, camera_, selected_handle_, width(), height());
        }
        backing_store_.endPaint();
        backing_store_.flush(region, this);
    }

    QBackingStore backing_store_;
    RoadSplineSegment segment_;
    ch::CameraState camera_;
    int selected_handle_ = -1;
    bool dragging_handle_ = false;
    bool panning_ = false;
    QPointF last_pointer_;
};

} // namespace

int main(int argc, char** argv) {
    // Preserve the original deterministic/headless mode used by CI and agents:
    // passing an output path writes one gameplay-scale PNG and exits without
    // constructing a GUI application.
    if (argc > 1) {
        const std::filesystem::path output = argv[1];
        if (!render_png(output)) {
            std::cerr << "Failed to write procedural road preview: " << output.string() << '\n';
            return 1;
        }
        std::cout << "Wrote procedural road preview: " << output.string() << '\n';
        return 0;
    }

    QGuiApplication app(argc, argv);
    RoadPilotWindow window;
    window.show();
    return app.exec();
}
