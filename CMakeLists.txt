cmake_minimum_required(VERSION 3.21)
project(Xbox2Windows LANGUAGES CXX)

enable_testing()
add_executable(root_probe tools/root_probe.cpp)
target_compile_features(root_probe PRIVATE cxx_std_17)
target_link_libraries(root_probe PRIVATE d3d12)
add_executable(d3d12_sdk_check tests/d3d12_sdk_check.cpp)
target_compile_features(d3d12_sdk_check PRIVATE cxx_std_17)
target_link_libraries(d3d12_sdk_check PRIVATE d3d12)
add_test(NAME desktop_root_signature COMMAND d3d12_sdk_check)
add_test(NAME desktop_bvh_root_flags COMMAND d3d12_sdk_check bvh-flags)

add_executable(era_heap_check tests/era_heap_check.cpp src/era_heap.cpp)
target_include_directories(era_heap_check PRIVATE src)
target_compile_features(era_heap_check PRIVATE cxx_std_20)
foreach(scenario IN ITEMS allocation failure concurrency caller_layout)
    add_test(NAME era_heap_${scenario} COMMAND era_heap_check ${scenario})
endforeach()

add_executable(memory_query_check tests/memory_query_check.cpp)
target_compile_features(memory_query_check PRIVATE cxx_std_17)
target_link_libraries(memory_query_check PRIVATE psapi)
add_test(NAME desktop_memory_query COMMAND memory_query_check)

find_program(DXC_EXECUTABLE dxc REQUIRED)
get_filename_component(DXC_BIN_DIR "${DXC_EXECUTABLE}" DIRECTORY)
target_compile_definitions(root_probe PRIVATE SDK_DXC_DIR=L"${DXC_BIN_DIR}/")
add_executable(offscreen_check tests/offscreen_check.cpp tests/compute_check.cpp tests/dxr_check.cpp tests/buffer_ops.cpp)
target_compile_features(offscreen_check PRIVATE cxx_std_17)
target_link_libraries(offscreen_check PRIVATE d3d12 dxgi dxguid)
target_include_directories(offscreen_check PRIVATE "${CMAKE_CURRENT_BINARY_DIR}")
set(OFFSCREEN_AGILITY_620_DIR "" CACHE PATH "Agility SDK 1.620.2 x64 DLL directory for debug validation")
if(OFFSCREEN_AGILITY_620_DIR)
    if(EXISTS "${OFFSCREEN_AGILITY_620_DIR}/sdk.nupkg")
        set(agility_headers "${CMAKE_CURRENT_BINARY_DIR}/agility-headers")
        file(ARCHIVE_EXTRACT INPUT "${OFFSCREEN_AGILITY_620_DIR}/sdk.nupkg" DESTINATION "${agility_headers}"
             PATTERNS "build/native/include/*.h")
        target_include_directories(offscreen_check BEFORE PRIVATE "${agility_headers}/build/native/include")
    endif()
    foreach(dll IN ITEMS D3D12Core.dll d3d12SDKLayers.dll)
        configure_file("${OFFSCREEN_AGILITY_620_DIR}/${dll}" "${CMAKE_CURRENT_BINARY_DIR}/D3D12/${dll}" COPYONLY)
    endforeach()
    target_compile_definitions(offscreen_check PRIVATE OFFSCREEN_AGILITY_620)
endif()
foreach(stage IN ITEMS vs ps)
    string(TOUPPER "${stage}" entry)
    set(header "${CMAKE_CURRENT_BINARY_DIR}/triangle_${stage}.h")
    set(binary "${CMAKE_CURRENT_BINARY_DIR}/triangle_${stage}.cso")
    add_custom_command(OUTPUT "${header}" "${binary}"
        COMMAND "${DXC_EXECUTABLE}" -T ${stage}_6_0 -E ${entry}Main -Vn triangle_${stage}
                -Fh "${header}" -Fo "${binary}" "${CMAKE_CURRENT_SOURCE_DIR}/tests/triangle.hlsl"
        DEPENDS tests/triangle.hlsl VERBATIM)
    target_sources(offscreen_check PRIVATE "${header}")
endforeach()
set(ray_header "${CMAKE_CURRENT_BINARY_DIR}/ray_query.h")
target_sources(offscreen_check PRIVATE tests/bvh_reads_waves.cpp tests/bvh_hits.cpp)
target_sources(offscreen_check PRIVATE tests/bvh_atomics.cpp tests/bvh_numeric.cpp)
foreach(entry IN ITEMS AtomicBounds QueryBounds NumericBounds)
    set(bounds_source tests/bvh_atomics.hlsl)
    if(entry STREQUAL "NumericBounds")
        set(bounds_source tests/bvh_numeric.hlsl)
    endif()
    set(header "${CMAKE_CURRENT_BINARY_DIR}/${entry}.h")
    add_custom_command(OUTPUT "${header}" COMMAND "${DXC_EXECUTABLE}" -T cs_6_5 -E ${entry}
        -Vn ${entry} -Fh "${header}" -Fo "${CMAKE_CURRENT_BINARY_DIR}/${entry}.cso"
        "${CMAKE_CURRENT_SOURCE_DIR}/${bounds_source}" DEPENDS "${bounds_source}"
        BYPRODUCTS "${CMAKE_CURRENT_BINARY_DIR}/${entry}.cso" VERBATIM)
    target_sources(offscreen_check PRIVATE "${header}")
endforeach()
foreach(entry IN ITEMS Produce ReadValues WaveValues Wave64 WriteScene TraceHits)
    set(header "${CMAKE_CURRENT_BINARY_DIR}/${entry}.h")
    set(wave_args -T cs_6_5 -E ${entry})
    if(entry STREQUAL "Wave64")
        set(wave_args -T cs_6_6 -E WaveValues -D REQUIRE_WAVE64=1)
    endif()
    add_custom_command(OUTPUT "${header}" COMMAND "${DXC_EXECUTABLE}" ${wave_args} -Vn ${entry}
        -Fh "${header}" -Fo "${CMAKE_CURRENT_BINARY_DIR}/${entry}.cso"
        "${CMAKE_CURRENT_SOURCE_DIR}/tests/bvh_reads_waves.hlsl" DEPENDS tests/bvh_reads_waves.hlsl
        BYPRODUCTS "${CMAKE_CURRENT_BINARY_DIR}/${entry}.cso" VERBATIM)
    target_sources(offscreen_check PRIVATE "${header}")
endforeach()
foreach(entry IN ITEMS CopyBlocks FillBlocks NumberBlocks CopySpan ResetBounds)
    set(header "${CMAKE_CURRENT_BINARY_DIR}/${entry}.h")
    add_custom_command(OUTPUT "${header}" COMMAND "${DXC_EXECUTABLE}" -T cs_6_5 -E ${entry} -Vn ${entry}
        -Fh "${header}" -Fo "${CMAKE_CURRENT_BINARY_DIR}/${entry}.cso"
        "${CMAKE_CURRENT_SOURCE_DIR}/tests/buffer_ops.hlsl" DEPENDS tests/buffer_ops.hlsl
        BYPRODUCTS "${CMAKE_CURRENT_BINARY_DIR}/${entry}.cso" VERBATIM)
    target_sources(offscreen_check PRIVATE "${header}")
endforeach()
add_custom_command(OUTPUT "${ray_header}"
    COMMAND "${DXC_EXECUTABLE}" -T cs_6_5 -E CSMain -Vn ray_query -Fh "${ray_header}"
            -Fo "${CMAKE_CURRENT_BINARY_DIR}/ray_query.cso" "${CMAKE_CURRENT_SOURCE_DIR}/tests/ray_query.hlsl"
    BYPRODUCTS "${CMAKE_CURRENT_BINARY_DIR}/ray_query.cso" DEPENDS tests/ray_query.hlsl VERBATIM)
target_sources(offscreen_check PRIVATE "${ray_header}")
foreach(layout IN ITEMS root tables)
    set(header "${CMAKE_CURRENT_BINARY_DIR}/compute_${layout}.h")
    set(binary "${CMAKE_CURRENT_BINARY_DIR}/compute_${layout}.cso")
    set(defines)
    if(layout STREQUAL "tables")
        set(defines -D TABLE_BINDINGS=1)
    endif()
    add_custom_command(OUTPUT "${header}" "${binary}"
        COMMAND "${DXC_EXECUTABLE}" -T cs_6_0 -E CSMain ${defines} -Vn compute_${layout}
                -Fh "${header}" -Fo "${binary}" "${CMAKE_CURRENT_SOURCE_DIR}/tests/compute.hlsl"
        DEPENDS tests/compute.hlsl VERBATIM)
    target_sources(offscreen_check PRIVATE "${header}")
    foreach(adapter IN ITEMS hardware warp)
        add_test(NAME compute_${layout}_${adapter} COMMAND offscreen_check ${adapter} --compute-${layout})
        set_tests_properties(compute_${layout}_${adapter} PROPERTIES TIMEOUT 45)
    endforeach()
    set_tests_properties(compute_${layout}_hardware PROPERTIES SKIP_RETURN_CODE 77)
endforeach()
foreach(adapter IN ITEMS hardware warp)
    add_test(NAME offscreen_${adapter} COMMAND offscreen_check ${adapter} triangle_${adapter}.bmp)
    add_test(NAME dxr_query_${adapter} COMMAND offscreen_check ${adapter} --ray-query)
    add_test(NAME dxr_update_${adapter} COMMAND offscreen_check ${adapter} --dxr-update)
    set_tests_properties(dxr_update_${adapter} PROPERTIES TIMEOUT 45 SKIP_RETURN_CODE 77)
    add_test(NAME bvh_buffer_ops_${adapter} COMMAND offscreen_check ${adapter} --buffer-ops)
    add_test(NAME bvh_root_roundtrip_${adapter} COMMAND offscreen_check ${adapter} --bvh-root-roundtrip)
    set_tests_properties(bvh_root_roundtrip_${adapter} PROPERTIES TIMEOUT 45)
    foreach(work IN ITEMS reads waves wave64 hits differential atomics numeric)
        add_test(NAME bvh_${work}_${adapter} COMMAND offscreen_check ${adapter} --bvh-${work})
        set_tests_properties(bvh_${work}_${adapter} PROPERTIES TIMEOUT 45)
    endforeach()
    set_tests_properties(bvh_wave64_${adapter} bvh_differential_${adapter} PROPERTIES SKIP_RETURN_CODE 77)
    set_tests_properties(bvh_buffer_ops_${adapter} PROPERTIES TIMEOUT 45)
    set_tests_properties(dxr_query_${adapter} PROPERTIES TIMEOUT 45 SKIP_RETURN_CODE 77)
    set_tests_properties(offscreen_${adapter} PROPERTIES TIMEOUT 45)
endforeach()
set_tests_properties(offscreen_hardware PROPERTIES SKIP_RETURN_CODE 77)
set_tests_properties(bvh_root_roundtrip_hardware PROPERTIES SKIP_RETURN_CODE 77)
set_tests_properties(bvh_atomics_hardware PROPERTIES SKIP_RETURN_CODE 77)
set_tests_properties(bvh_numeric_hardware PROPERTIES SKIP_RETURN_CODE 77)
set_tests_properties(bvh_buffer_ops_hardware PROPERTIES SKIP_RETURN_CODE 77)
set_tests_properties(bvh_reads_hardware bvh_waves_hardware bvh_hits_hardware PROPERTIES SKIP_RETURN_CODE 77)

set(SIMPLE_TRIANGLE_DIR "${CMAKE_SOURCE_DIR}/out/reference/b1e77b6ac10f95b07296025fda171ca2ddc42dbe/Samples/IntroGraphics/SimpleTriangle"
    CACHE PATH "Microsoft SimpleTriangle sample directory")
if(EXISTS "${SIMPLE_TRIANGLE_DIR}/VertexShader.hlsl")
    find_program(REFERENCE_POWERSHELL NAMES pwsh powershell REQUIRED)
    foreach(adapter IN ITEMS hardware warp)
        add_test(NAME reference_triangle_${adapter} COMMAND "${REFERENCE_POWERSHELL}" -NoProfile -ExecutionPolicy Bypass
            -File "${CMAKE_SOURCE_DIR}/tests/reference_triangle.ps1" -Sample "${SIMPLE_TRIANGLE_DIR}"
            -Compiler "${DXC_EXECUTABLE}" -Renderer "$<TARGET_FILE:offscreen_check>" -Adapter ${adapter})
        set_tests_properties(reference_triangle_${adapter} PROPERTIES TIMEOUT 60 SKIP_RETURN_CODE 77)
    endforeach()
endif()

set(INTAKE_PYTHON "${CMAKE_SOURCE_DIR}/out/pe-env/Scripts/python.exe" CACHE FILEPATH
    "Native x64 Python with pefile for static intake tests")
if(EXISTS "${INTAKE_PYTHON}")
    add_test(NAME shader_metadata_probe COMMAND "${INTAKE_PYTHON}" -B
        "${CMAKE_SOURCE_DIR}/tests/shader_probe_check.py" "$<TARGET_FILE:root_probe>"
        "${CMAKE_CURRENT_BINARY_DIR}/compute_root.cso" "${CMAKE_CURRENT_BINARY_DIR}/compute_tables.cso"
        "${CMAKE_CURRENT_BINARY_DIR}/triangle_vs.cso")
    add_test(NAME conditional_import_paths COMMAND "${INTAKE_PYTHON}" -B "${CMAKE_SOURCE_DIR}/tests/intake/paths_check.py")
    add_library(intake_provider SHARED tests/intake/provider.cpp tests/intake/provider.def)
    add_library(intake_delay SHARED tests/intake/provider.cpp tests/intake/delay.def)
    add_executable(intake_candidate tests/intake/candidate.cpp)
    # Build an import library from a name only. No graphics DLL is linked or executed at build time.
    set(graphics_import "${CMAKE_CURRENT_BINARY_DIR}/intake_graphics.lib")
    add_custom_command(OUTPUT "${graphics_import}"
        COMMAND "${CMAKE_AR}" /nologo /machine:x64 "/def:${CMAKE_CURRENT_SOURCE_DIR}/tests/intake/graphics_import.def"
                "/out:${graphics_import}"
        DEPENDS tests/intake/graphics_import.def VERBATIM)
    target_sources(intake_candidate PRIVATE "${graphics_import}")
    target_link_libraries(intake_candidate PRIVATE intake_provider intake_delay delayimp "${graphics_import}")
    target_link_options(intake_candidate PRIVATE /DELAYLOAD:intake_delay.dll)
    add_test(NAME static_exe_intake COMMAND "${INTAKE_PYTHON}" -B
        "${CMAKE_SOURCE_DIR}/tests/intake/check.py" "$<TARGET_FILE:intake_candidate>"
        "$<TARGET_FILE:intake_provider>")
endif()
