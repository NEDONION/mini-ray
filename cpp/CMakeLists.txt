# 包含头文件目录
include_directories(${CMAKE_CURRENT_SOURCE_DIR}/include)

# 收集源文件
set(MINIRAY_SOURCES
    src/python_bindings.cpp
)

# 创建 Python 扩展模块
pybind11_add_module(_miniray_core ${MINIRAY_SOURCES})

# 设置输出名称和路径
set_target_properties(_miniray_core PROPERTIES
    PREFIX ""
    OUTPUT_NAME "_miniray_core"
    LIBRARY_OUTPUT_DIRECTORY ${CMAKE_SOURCE_DIR}/python/mini_ray
)

# 如果是 macOS，设置 rpath
if(APPLE)
    set_target_properties(_miniray_core PROPERTIES
        INSTALL_RPATH "@loader_path"
        BUILD_WITH_INSTALL_RPATH TRUE
    )
endif()

# 链接线程库
find_package(Threads REQUIRED)
target_link_libraries(_miniray_core PRIVATE Threads::Threads)
