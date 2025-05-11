/**
 * Git Ingest File Tree Handler
 * Handles the directory tree functionality
 */

function initializeFileTree() {
    // Initialize tree event listeners with debug logging
    resetTreeEventListeners();
    
    // Initialize extension filter
    initializeExtensionFilter();
    
    // Initialize extension hide functionality
    initializeExtensionHide();

    // Initialize quick controls
    $('#select-all').on('click', function() {
        $('#file-tree .file-checkbox, #file-tree .dir-checkbox').prop('checked', true);
        updateSelectedCount();
    });

    $('#deselect-all').on('click', function() {
        $('#file-tree .file-checkbox, #file-tree .dir-checkbox').prop('checked', false);
        updateSelectedCount();
    });

    $('#expand-all').on('click', expandAllFolders);
    
    $('#collapse-all').on('click', collapseAllFolders);

    // Initialize info section toggle
    initializeInfoSection();
}

function initializeInfoSection() {
    $('.info-header').on('click', function() {
        const content = $(this).siblings('.info-content');
        const icon = $(this).find('.toggle-info-button i');

        content.slideToggle(200, function() {
            if (content.is(':visible')) {
                icon.removeClass('fa-chevron-down').addClass('fa-chevron-up');
                $(this).closest('.info-header').css('margin-bottom', '10px'); // Add margin when open
            } else {
                icon.removeClass('fa-chevron-up').addClass('fa-chevron-down');
                $(this).closest('.info-header').css('margin-bottom', '0'); // Remove margin when closed
            }
        });
    });
}

// Extension filter functionality
function initializeExtensionFilter() {
    // Current extensions array
    let activeExtensions = [];
    
    // Handle adding extension via input
    $('#extension-input').on('keypress', function(e) {
        if (e.which === 13) { // Enter key
            e.preventDefault();
            addExtension();
        }
    });
    
    $('#add-extension').on('click', function() {
        addExtension();
    });
    
    // Clear all extensions
    $('#clear-extensions').on('click', function() {
        activeExtensions = [];
        renderExtensionPills();
        showToast('All extension filters cleared', 'info');
    });
    
    // Add extension from input field
    function addExtension() {
        let ext = $('#extension-input').val().trim();
        
        // Validate extension
        if (ext) {
            // Add leading dot if missing
            if (!ext.startsWith('.')) {
                ext = '.' + ext;
            }
            
            // Add if not already in the list
            if (!activeExtensions.includes(ext)) {
                activeExtensions.push(ext);
                renderExtensionPills();
                showToast(`Added "${ext}" filter`, 'success');
                
                // Clear input field
                $('#extension-input').val('');
            } else {
                showToast(`"${ext}" is already in filters`, 'info');
            }
        }
    }
    
    // Handle quick-add buttons
    $('.ext-pill-btn').on('click', function() {
        const ext = $(this).data('ext');
        
        if (!activeExtensions.includes(ext)) {
            activeExtensions.push(ext);
            renderExtensionPills();
            showToast(`Added "${ext}" to selection list`, 'success');
        }
    });
    
    // Render extension pills
    function renderExtensionPills() {
        const pillsContainer = $('#extension-pills');
        pillsContainer.empty();
        
        activeExtensions.forEach(ext => {
            const pill = $(`<span class="extension-pill">${ext}<span class="remove-ext"><i class="fas fa-times"></i></span></span>`);
            pillsContainer.append(pill);
            
            // Add remove handler
            pill.find('.remove-ext').on('click', function() {
                activeExtensions = activeExtensions.filter(e => e !== ext);
                renderExtensionPills();
            });
        });
    }
    
    // Handle the "Select Files with These Extensions" button
    $('#apply-extension-selection').on('click', function() {
        if (activeExtensions.length === 0) {
            showToast('Please add at least one extension first', 'info');
            return;
        }
        
        selectFilesByExtension();
    });
    
    // Select files by extension
    function selectFilesByExtension() {
        if (activeExtensions.length === 0) {
            return;
        }
        
        let selectedCount = 0;
        
        // Find all files with matching extensions and check them
        $('#file-tree .file').each(function() {
            const fileName = $(this).find('.file-name').text();
            
            // Check if any active extension matches
            const hasMatchingExt = activeExtensions.some(ext => 
                fileName.toLowerCase().endsWith(ext.toLowerCase())
            );
            
            if (hasMatchingExt) {
                const checkbox = $(this).find('.file-checkbox');
                if (!checkbox.prop('checked')) {
                    checkbox.prop('checked', true);
                    selectedCount++;
                }
            }
        });
        
        // Update selected count
        updateSelectedCount();
        
        // Show toast with results
        if (selectedCount > 0) {
            showToast(`Selected ${selectedCount} additional files`, 'success');
        } else {
            showToast('No new files matched the extensions', 'info');
        }
    }
}

// Extension hiding functionality
function initializeExtensionHide() {
    // Current extensions to hide
    let hideExtensions = [];
    
    // Handle adding extension via input
    $('#extension-hide-input').on('keypress', function(e) {
        if (e.which === 13) { // Enter key
            e.preventDefault();
            addHideExtension();
        }
    });
    
    $('#add-hide-extension').on('click', function() {
        addHideExtension();
    });
    
    // Clear all hide extensions
    $('#clear-hide-extensions').on('click', function() {
        hideExtensions = [];
        renderHideExtensionPills();
        showToast('All hide filters cleared', 'info');
    });
    
    // Add extension to hide list
    function addHideExtension() {
        let ext = $('#extension-hide-input').val().trim();
        
        // Validate extension
        if (ext) {
            // Add leading dot if missing
            if (!ext.startsWith('.')) {
                ext = '.' + ext;
            }
            
            // Add if not already in the list
            if (!hideExtensions.includes(ext)) {
                hideExtensions.push(ext);
                renderHideExtensionPills();
                showToast(`Added "${ext}" to hide list`, 'success');
                
                // Clear input field
                $('#extension-hide-input').val('');
            } else {
                showToast(`"${ext}" is already in hide list`, 'info');
            }
        }
    }
    
    // Handle quick-add buttons for hide extensions
    $('.hide-ext-pill-btn').on('click', function() {
        const ext = $(this).data('ext');
        
        if (!hideExtensions.includes(ext)) {
            hideExtensions.push(ext);
            renderHideExtensionPills();
            showToast(`Added "${ext}" to hide list`, 'success');
        }
    });
    
    // Render hide extension pills
    function renderHideExtensionPills() {
        const pillsContainer = $('#hide-extension-pills');
        pillsContainer.empty();
        
        hideExtensions.forEach(ext => {
            const pill = $(`<span class="extension-pill">${ext}<span class="remove-ext"><i class="fas fa-times"></i></span></span>`);
            pillsContainer.append(pill);
            
            // Add remove handler
            pill.find('.remove-ext').on('click', function() {
                hideExtensions = hideExtensions.filter(e => e !== ext);
                renderHideExtensionPills();
            });
        });
    }
    
    // Handle the "Hide Files with These Extensions" button
    $('#apply-extension-hide').on('click', function() {
        if (hideExtensions.length === 0) {
            showToast('Please add at least one extension to hide', 'info');
            return;
        }
        
        hideFilesByExtension();
    });
    
    // Handle the "Show All Files" button
    $('#show-all-files').on('click', function() {
        showAllFiles();
    });
    
    // Hide files by extension
    function hideFilesByExtension() {
        if (hideExtensions.length === 0) {
            return;
        }
        
        let hiddenCount = 0;
        let deselectedCount = 0;
        
        // Find all files with matching extensions and hide them
        $('#file-tree .file').each(function() {
            const fileName = $(this).find('.file-name').text();
            
            // Check if any hide extension matches
            const hasMatchingExt = hideExtensions.some(ext => 
                fileName.toLowerCase().endsWith(ext.toLowerCase())
            );
            
            if (hasMatchingExt) {
                // Hide the file
                $(this).hide();
                hiddenCount++;
                
                // Also deselect/uncheck the file
                const checkbox = $(this).find('.file-checkbox');
                if (checkbox.prop('checked')) {
                    checkbox.prop('checked', false);
                    deselectedCount++;
                }
            }
        });
        
        // Update directory visibility
        updateDirectoryVisibility();
        
        // Update selected count since we might have unchecked files
        updateSelectedCount();
        
        // Show toast with results
        if (hiddenCount > 0) {
            let message = `Hidden ${hiddenCount} files from view`;
            if (deselectedCount > 0) {
                message += ` and deselected ${deselectedCount} files`;
            }
            showToast(message, 'success');
        } else {
            showToast('No files matched the extensions to hide', 'info');
        }
    }
    
    // Show all files
    function showAllFiles() {
        // Show all files
        $('#file-tree .file').show();
        
        // Show all directories
        $('#file-tree .directory').show();
        
        showToast('All files are now visible', 'info');
    }
    
    // Update directory visibility (hide empty directories)
    function updateDirectoryVisibility() {
        // Process directories bottom-up
        let directories = $('#file-tree .directory').get().reverse();
        
        $(directories).each(function() {
            const dir = $(this);
            const hasVisibleFiles = dir.find('.file:visible').length > 0;
            const hasVisibleDirs = dir.find('.directory:visible').length > 0;
            
            if (hasVisibleFiles || hasVisibleDirs) {
                dir.show();
            } else {
                dir.hide();
            }
        });
    }
}

function expandAllFolders() {
    // First show all directory subtrees
    $('#file-tree .directory > ul').show();
    
    // Update all carets - need to target SVG with FA6
    $('#file-tree .expand-button').each(function() {
        $(this).find('svg.fa-caret-right').removeClass('fa-caret-right').addClass('fa-caret-down');
    });
    
    console.log("Expand all: Updated " + $('#file-tree .expand-button').length + " buttons");
}

function collapseAllFolders() {
    // First hide all directory subtrees
    $('#file-tree .directory > ul').hide();
    
    // Update all carets - need to target SVG with FA6
    $('#file-tree .expand-button').each(function() {
        $(this).find('svg.fa-caret-down').removeClass('fa-caret-down').addClass('fa-caret-right');
    });
    
    console.log("Collapse all: Updated " + $('#file-tree .expand-button').length + " buttons");
}

// Function to get pathignore patterns from textarea
function getPathignorePatterns() {
    const usePathignore = $('#pathignore-toggle').is(':checked');
    if (!usePathignore) return [];
    
    return $('#pathignore-input').val()
        .split('\n')
        .map(line => line.trim())
        .filter(line => line !== '' && !line.startsWith('#'));
}

// Function to test if a path would be ignored by pathignore patterns
function testPathPatterns(patterns, path) {
    if (!patterns || patterns.length === 0) return false;
    
    for (const pattern of patterns) {
        // Skip empty or comment lines
        if (!pattern || pattern.trim() === '' || pattern.trim().startsWith('#')) continue;
        
        // Convert glob pattern to regex
        let regexPattern = pattern
            .replace(/\./g, '\\.')
            .replace(/\*/g, '.*')
            .replace(/\?/g, '.');
            
        // Handle directory patterns
        if (pattern.endsWith('/')) {
            regexPattern = `^(.*/)?(${regexPattern.slice(0, -1)})(/.*)?$`;
        } else {
            regexPattern = `^(.*/)?(${regexPattern})$`;
        }
        
        const regex = new RegExp(regexPattern);
        if (regex.test(path)) return true;
    }
    
    return false;
}

function resetTreeEventListeners() {
    // First completely remove all existing handlers
    $(document).off('click', '#file-tree .expand-button');
    $(document).off('click', '#file-tree .directory-name');
    $(document).off('change', '.dir-checkbox, .file-checkbox');

    // Handle expand/collapse folder clicks
    $(document).on('click', '#file-tree .expand-button', function(event) {
        event.stopPropagation();
        event.preventDefault();
        
        let directoryItem = $(this).closest('.directory');
        let subtree = directoryItem.children('ul');
        
        console.log("Clicked folder toggle. Current visibility:", subtree.is(':visible'));
        
        // With Font Awesome 6, we need to target SVG element
        let iconElement = $(this).find('svg');
        
        if (subtree.is(':visible')) {
            subtree.hide();
            console.log("Hiding folder, changing icon to right arrow");
            if (iconElement.hasClass('fa-caret-down')) {
                iconElement.removeClass('fa-caret-down').addClass('fa-caret-right');
            }
        } else {
            subtree.show();
            console.log("Showing folder, changing icon to down arrow");
            if (iconElement.hasClass('fa-caret-right')) {
                iconElement.removeClass('fa-caret-right').addClass('fa-caret-down');
            }
        }
    });

    // Directory name click handler
    $(document).on('click', '#file-tree .directory-name', function(event) {
        event.stopPropagation();
        $('.selected').removeClass('selected');
        $(this).addClass('selected');

        // If you want to expand/collapse on directory name click too:
        let expander = $(this).siblings('.expand-button');
        if (expander.length) {
            expander.trigger('click');
        }
    });

    // Checkbox change handler (for both directory and file checkboxes)
    $(document).on('change', '.dir-checkbox, .file-checkbox', function(event) {
        event.stopPropagation(); // Prevent expand/collapse on checkbox click
        
        let isChecked = $(this).is(':checked');
        if ($(this).hasClass('dir-checkbox')) {
            // If it's a directory checkbox, update all descendant checkboxes
            $(this).closest('.directory').find('.file-checkbox, .dir-checkbox').prop('checked', isChecked);
        }

        // Update selected files count
        updateSelectedCount();
    });
    
    console.log("Tree event listeners initialized");
}

function updateSelectedCount() {
    const count = $('.file-checkbox:checked').length;
    $('#selected-count').text(count + (count === 1 ? ' file selected' : ' files selected'));
    
    if (count > 0) {
        $('#selected-count').addClass('selected');
    } else {
        $('#selected-count').removeClass('selected');
    }
}

// Helper function to show toast notifications
function showToast(message, type = 'info') {
    const toast = $('<div>')
        .addClass(`toast toast-${type}`)
        .text(message);

    $('.toast-container').append(toast);

    // Trigger animation
    setTimeout(() => toast.addClass('show'), 10);

    // Auto remove after delay
    setTimeout(() => {
        toast.removeClass('show');
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}
