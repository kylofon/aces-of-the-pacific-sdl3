cmake_minimum_required(VERSION 3.24)
project(aotpport C)

set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)

# Faithful port of Aces of the Pacific (INTRO.EXE, PS.EXE, AP.EXE in one process), VGA with AdLib
# sound (PLAN.md decisions 1, 2, 7). The executables are read from the game folder at run time.

find_package(SDL3 REQUIRED CONFIG)

# Nuked-OPL3 (LGPL-2.1), built as its own library and linked in; see third_party/nuked-opl3/README.md.
add_library(nuked_opl3 STATIC third_party/nuked-opl3/opl3.c)
target_include_directories(nuked_opl3 PUBLIC third_party/nuked-opl3)

file(GLOB_RECURSE AOTP_SOURCES CONFIGURE_DEPENDS src/*.c)

add_executable(aotp ${AOTP_SOURCES})
target_include_directories(aotp PRIVATE src)
target_link_libraries(aotp PRIVATE SDL3::SDL3 nuked_opl3)
if(MSVC)
    target_compile_options(aotp PRIVATE /W3)
else()
    # The memory model reads multi-byte values through byte pointers (see src/mem.h).
    target_compile_options(aotp PRIVATE -Wall -Wextra -Wno-unused-parameter -fno-strict-aliasing)
    if(CMAKE_C_COMPILER_ID STREQUAL "GNU")
        target_compile_options(aotp PRIVATE -Wno-format-truncation)
    endif()
endif()
if(WIN32)
    add_custom_command(TARGET aotp POST_BUILD
        COMMAND ${CMAKE_COMMAND} -E copy_if_different $<TARGET_RUNTIME_DLLS:aotp> $<TARGET_FILE_DIR:aotp>
        COMMAND_EXPAND_LISTS)
endif()
