proc _require_env {name} {
    if {![info exists ::env($name)] || $::env($name) == ""} {
        error [format "missing environment variable %s" $name]
    }
    return $::env($name)
}

proc _find_block_by_name {target_name} {
    foreach obj [db_list_objects_recursive] {
        if {[$obj getval mat_lib_path ""] != ""} {
            continue
        }
        if {[$obj getval obtype] != "block"} {
            continue
        }
        if {[$obj getval name] == $target_name} {
            return $obj
        }
    }
    return ""
}

proc _approx_equal {left right tolerance} {
    return [expr {abs($left - $right) <= $tolerance}]
}

proc _bbox_to_points {bbox} {
    set pmin [lindex $bbox 0]
    set pmax [lindex $bbox 1]
    if {[llength $pmin] != 3 || [llength $pmax] != 3} {
        error "invalid bbox"
    }
    return [list $pmin $pmax]
}

proc _set_hexa_bbox {shape bbox} {
    set p1 [lindex $bbox 0]
    set p2 [lindex $bbox 1]
    set diff [list \
        [expr {[lindex $p2 0] - [lindex $p1 0]}] \
        [expr {[lindex $p2 1] - [lindex $p1 1]}] \
        [expr {[lindex $p2 2] - [lindex $p1 2]}] \
    ]
    $shape setval \
        point1 $p1 \
        point2 $p2 \
        diff $diff \
        volume_flag [$shape getval volume_flag] \
        diff_flag [$shape getval diff_flag] \
        offset [$shape getval offset]
}

set selected_name [_require_env QD_SELECTED_BLOCK]
set partner_name [_require_env QD_PARTNER_BLOCK]
set stack_axis [string tolower [_require_env QD_STACK_AXIS]]
set direction_sign [_require_env QD_DIRECTION_SIGN]
set delta_m [expr {double([_require_env QD_DELTA_M])}]

if {$stack_axis == "x"} {
    set stack_index 0
} elseif {$stack_axis == "y"} {
    set stack_index 1
} elseif {$stack_axis == "z"} {
    set stack_index 2
} else {
    error [format "unsupported stack axis: %s" $stack_axis]
}

if {$direction_sign != "+" && $direction_sign != "-"} {
    error [format "unsupported direction sign: %s" $direction_sign]
}

set selected_obj [_find_block_by_name $selected_name]
set partner_obj [_find_block_by_name $partner_name]
if {$selected_obj == ""} {
    error [format "selected block not found: %s" $selected_name]
}
if {$partner_obj == ""} {
    error [format "partner block not found: %s" $partner_name]
}

set selected_shape [$selected_obj getval body_shape]
set partner_shape [$partner_obj getval body_shape]

if {[$selected_shape get -shtype] != "hexa"} {
    error [format "selected block shape must be hexa: %s" [$selected_shape get -shtype]]
}
if {[$partner_shape get -shtype] != "hexa"} {
    error [format "partner block shape must be hexa: %s" [$partner_shape get -shtype]]
}

set tolerance 1.0e-9
set selected_bbox [$selected_shape get_bbox]
set partner_bbox [$partner_shape get_bbox]
set selected_min [lindex $selected_bbox 0]
set selected_max [lindex $selected_bbox 1]
set partner_min [lindex $partner_bbox 0]
set partner_max [lindex $partner_bbox 1]

foreach axis {0 1 2} {
    if {$axis == $stack_index} {
        continue
    }
    if {![_approx_equal [lindex $selected_min $axis] [lindex $partner_min $axis] $tolerance] \
        || ![_approx_equal [lindex $selected_max $axis] [lindex $partner_max $axis] $tolerance]} {
        error "selected block and partner block do not have identical cross-section ranges"
    }
}

if {$direction_sign == "+"} {
    if {![_approx_equal [lindex $selected_max $stack_index] [lindex $partner_min $stack_index] $tolerance]} {
        error [format "selected block and partner block are not adjacent on the +%s side" [string toupper $stack_axis]]
    }
    set new_shared_coordinate [expr {[lindex $selected_max $stack_index] + $delta_m}]
    if {$new_shared_coordinate <= [expr {[lindex $selected_min $stack_index] + $tolerance}]} {
        error [format "selected block thickness along %s would become non-positive" [string toupper $stack_axis]]
    }
    if {$new_shared_coordinate >= [expr {[lindex $partner_max $stack_index] - $tolerance}]} {
        error [format "partner block thickness along %s would become non-positive" [string toupper $stack_axis]]
    }
    set selected_max [lreplace $selected_max $stack_index $stack_index $new_shared_coordinate]
    set partner_min [lreplace $partner_min $stack_index $stack_index $new_shared_coordinate]
} else {
    if {![_approx_equal [lindex $selected_min $stack_index] [lindex $partner_max $stack_index] $tolerance]} {
        error [format "selected block and partner block are not adjacent on the -%s side" [string toupper $stack_axis]]
    }
    set new_shared_coordinate [expr {[lindex $selected_min $stack_index] - $delta_m}]
    if {$new_shared_coordinate >= [expr {[lindex $selected_max $stack_index] - $tolerance}]} {
        error [format "selected block thickness along %s would become non-positive" [string toupper $stack_axis]]
    }
    if {$new_shared_coordinate <= [expr {[lindex $partner_min $stack_index] + $tolerance}]} {
        error [format "partner block thickness along %s would become non-positive" [string toupper $stack_axis]]
    }
    set selected_min [lreplace $selected_min $stack_index $stack_index $new_shared_coordinate]
    set partner_max [lreplace $partner_max $stack_index $stack_index $new_shared_coordinate]
}

_set_hexa_bbox $selected_shape [list $selected_min $selected_max]
_set_hexa_bbox $partner_shape [list $partner_min $partner_max]

db_dirty model
icepak_save 0

puts [format "ADJUSTED selected=%s partner=%s stack_axis=%s direction_sign=%s delta_m=%s" \
    $selected_name $partner_name $stack_axis $direction_sign $delta_m]
puts [format "SELECTED_BBOX %s" [$selected_shape get_bbox]]
puts [format "PARTNER_BBOX %s" [$partner_shape get_bbox]]
exit 0