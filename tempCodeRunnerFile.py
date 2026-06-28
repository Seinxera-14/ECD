    """Generate HTML for display with bilingual support and double-click editing"""
            
            # Extract parameters from parsed_data
            language = parsed_data.get('language', 'en')
            voltage = parsed_data.get('voltage', '230V / 415V')
            
            # Build bilingual key for the HTML display
            key = {
                'generated': "Generated Diagram" if language == 'en' else "生成された図",
                'tip': "Tip: Double-click on any element to edit it!" if language == 'en' else "ヒント：要素をダブルクリックして編集できます！",
                'logic_title': "Logic Flow" if language == 'en' else "論理フロー",
                'logic_items': [
                    "Power enters from supply" if language == 'en' else "電源から電力が入る",
                    "Protected by main breaker" if language == 'en' else "主遮断器で保護",
                    "Distributed via busbar" if language == 'en' else "母線を介して分配"
                ],
                'safety_title': "Safety Features" if language == 'en' else "安全機能",
                'safety_items': [
                    "Neutral return path" if language == 'en' else "中性線帰路",
                    "Earth grounding" if language == 'en' else "接地",
                    "Circuit protection" if language == 'en' else "回路保護"
                ],
                'components_title': "Key Components" if language == 'en' else "主要コンポーネント",
                'components_items': [
                    "Circuit breakers (MCB/MCCB)" if language == 'en' else "回路遮断器 (MCB/MCCB)",
                    "Busbar distribution" if language == 'en' else "母線配電",
                    "Load circuits" if language == 'en' else "負荷回路"
                ]
            }
            
            # Set default title if not provided
            if not title:
                title = "Electrical Distribution Diagram" if language == 'en' else "電気配電図"
            
            # JavaScript for editing with proper escaping
            editing_js = ""
            if enable_editing:
                editing_js = r"""
                <script>
                    class EnhancedMermaidEditor {
                        constructor() {
                            this.currentEdit = null;
                            this.currentDrag = null;
                            this.potentialDrag = null;
                            this.dragStartTime = 0;
                            this.dragThreshold = 300;
                            this.resizeHandles = null;
                            this.dragIndicator = null;
                            this.svg = null;
                            this.svgPoint = null;
                            this.setupEventListeners();
                        }
                        
                        setupEventListeners() {
                            const checkInterval = setInterval(() => {
                                const svg = document.querySelector('.mermaid svg');
                                if (svg) {
                                    clearInterval(checkInterval);
                                    this.initSVG(svg);
                                    setTimeout(() => {
                                        this.ensureTextVisibility(svg);
                                        this.centerAllTextInBoxes(svg);
                                    }, 500);
                                }
                            }, 100);
                        }

                        initSVG(svg) {
                            console.log('Initializing SVG editor');
                            this.svg = svg;
                            this.svgPoint = svg.createSVGPoint();
                            
                            // Ensure all text is visible
                            this.ensureTextVisibility(svg);
                            
                            // Setup event listeners
                            svg.addEventListener('dblclick', (e) => this.handleDoubleClick(e, svg));
                            svg.addEventListener('mousedown', (e) => this.handleMouseDown(e));
                            svg.addEventListener('mousemove', (e) => this.handleMouseMove(e));
                            svg.addEventListener('mouseup', (e) => this.handleMouseUp(e));
                            svg.addEventListener('mouseleave', (e) => this.handleMouseUp(e));
                            
                            this.setupHoverEffects();
                        }
                        
                        ensureTextVisibility(svg) {
                            const allText = svg.querySelectorAll('text, tspan');
                            allText.forEach(el => {
                                const currentFill = el.getAttribute('fill');
                                if (!currentFill || currentFill === 'currentColor' || currentFill === 'inherit' ||
                                    currentFill === '#ffffff' || currentFill === '#fff' || 
                                    currentFill.startsWith('rgb(255') || currentFill === 'white') {
                                    el.setAttribute('fill', '#333333');
                                }
                            });
                        }
                        
                        screenToSVG(svg, x, y) {
                            const pt = this.svgPoint;
                            pt.x = x;
                            pt.y = y;
                            try {
                                return pt.matrixTransform(svg.getScreenCTM().inverse());
                            } catch (e) {
                                return {x: x, y: y};
                            }
                        }
                        
                        isBoxElement(element) {
                            if (!element) return false;
                            const tagName = element.tagName;
                            const className = element.getAttribute('class') || '';
                            
                            if (tagName === 'rect') {
                                const fill = element.getAttribute('fill') || '';
                                if (fill.includes('fff7ed') || fill.includes('f0fdf4') || 
                                    fill.includes('eef2ff') || fill.includes('fffacd') ||
                                    fill.includes('ffff00') || fill === '#fffacd' || fill === 'yellow') {
                                    return true;
                                }
                                if (className.includes('labelBox') || className.includes('box') || 
                                    className.includes('actor') || className.includes('note')) {
                                    return true;
                                }
                            }
                            
                            if (tagName === 'g') {
                                const rectChild = element.querySelector('rect');
                                if (rectChild && this.isBoxElement(rectChild)) {
                                    return true;
                                }
                                if (className.includes('note')) {
                                    return true;
                                }
                            }
                            
                            return false;
                        }
                        
                        getBoxData(element) {
                            if (!element) return null;
                            
                            let rectElement, textElements = [];
                            let isNoteBox = false;
                            
                            const className = element.getAttribute('class') || '';
                            const fill = element.getAttribute('fill') || '';
                            
                            if (className.includes('note') || fill.includes('fffacd') || 
                                fill.includes('ffff00') || fill === 'yellow') {
                                isNoteBox = true;
                            }
                            
                            if (element.tagName === 'rect') {
                                rectElement = element;
                            } else {
                                rectElement = element.querySelector('rect');
                            }
                            
                            if (!rectElement) return null;
                            
                            // Get box coordinates
                            const x = parseFloat(rectElement.getAttribute('x')) || 0;
                            const y = parseFloat(rectElement.getAttribute('y')) || 0;
                            const width = parseFloat(rectElement.getAttribute('width')) || 0;
                            const height = parseFloat(rectElement.getAttribute('height')) || 0;
                            
                            return {
                                element: rectElement,
                                groupElement: element.tagName === 'rect' ? element.parentElement : element,
                                x: x,
                                y: y,
                                width: width,
                                height: height,
                                textElements: textElements,
                                isNoteBox: isNoteBox
                            };
                        }
                        
                        findAllBoxes() {
                            if (!this.svg) return [];
                            const boxes = [];
                            const rects = this.svg.querySelectorAll('rect');
                            
                            rects.forEach(rect => {
                                if (this.isBoxElement(rect)) {
                                    boxes.push(rect);
                                }
                            });
                            
                            const groups = this.svg.querySelectorAll('g');
                            groups.forEach(group => {
                                if (this.isBoxElement(group)) {
                                    boxes.push(group);
                                }
                            });
                            
                            return boxes;
                        }
                        
                        findTextInBox(boxElement) {
                            const boxData = this.getBoxData(boxElement);
                            if (!boxData) return [];
                            
                            const texts = [];
                            
                            if (boxData.isNoteBox) {
                                if (boxData.groupElement && boxData.groupElement.tagName === 'g') {
                                    const textElements = boxData.groupElement.querySelectorAll('text');
                                    textElements.forEach(text => texts.push(text));
                                }
                                
                                if (texts.length === 0) {
                                    const allTexts = this.svg.querySelectorAll('text');
                                    allTexts.forEach(text => {
                                        try {
                                            const textRect = text.getBBox();
                                            if (textRect.x >= boxData.x - 10 && 
                                                textRect.x + textRect.width <= boxData.x + boxData.width + 10 &&
                                                textRect.y >= boxData.y - 10 && 
                                                textRect.y + textRect.height <= boxData.y + boxData.height + 10) {
                                                texts.push(text);
                                            }
                                        } catch (e) {
                                            const textX = parseFloat(text.getAttribute('x') || 0);
                                            const textY = parseFloat(text.getAttribute('y') || 0);
                                            
                                            if (textX >= boxData.x && textX <= boxData.x + boxData.width &&
                                                textY >= boxData.y && textY <= boxData.y + boxData.height) {
                                                texts.push(text);
                                            }
                                        }
                                    });
                                }
                            } else {
                                const allTexts = this.svg.querySelectorAll('text');
                                allTexts.forEach(text => {
                                    try {
                                        const textRect = text.getBBox();
                                        if (textRect.x >= boxData.x - 10 && 
                                            textRect.x + textRect.width <= boxData.x + boxData.width + 10 &&
                                            textRect.y >= boxData.y - 10 && 
                                            textRect.y + textRect.height <= boxData.y + boxData.height + 10) {
                                            texts.push(text);
                                        }
                                    } catch (e) {
                                        const textX = parseFloat(text.getAttribute('x') || 0);
                                        const textY = parseFloat(text.getAttribute('y') || 0);
                                        
                                        if (textX >= boxData.x && textX <= boxData.x + boxData.width &&
                                            textY >= boxData.y && textY <= boxData.y + boxData.height) {
                                            texts.push(text);
                                        }
                                    }
                                });
                            }
                            
                            return texts;
                        }
                        
                        centerAllTextInBoxes(svg) {
                            console.log('Centering text in boxes');
                            const boxes = this.findAllBoxes();
                            boxes.forEach(box => {
                                const texts = this.findTextInBox(box);
                                if (texts.length > 0) {
                                    this.centerTextInBox(box, texts);
                                }
                            });
                            
                            const noteBoxes = this.findNoteBoxes();
                            noteBoxes.forEach(box => {
                                const texts = this.findTextInBox(box);
                                if (texts.length > 0) {
                                    this.centerTextInBox(box, texts);
                                }
                            });
                        }
                        
                        centerTextInBox(boxElement, textElements) {
                            const boxData = this.getBoxData(boxElement);
                            if (!boxData || !textElements || textElements.length === 0) return;
                            
                            console.log('Centering', textElements.length, 'text elements in box');
                            
                            // Calculate box center
                            const boxCenterX = boxData.x + boxData.width / 2;
                            const boxCenterY = boxData.y + boxData.height / 2;
                            
                            // Group text elements by their parent (for tspans)
                            const textGroups = {};
                            textElements.forEach(text => {
                                let parentElement = text;
                                let isTspan = false;
                                
                                if (text.tagName === 'tspan') {
                                    parentElement = text.parentElement;
                                    isTspan = true;
                                }
                                
                                if (!parentElement) return;
                                
                                // Create a key for grouping
                                const key = parentElement.tagName + '_' + 
                                        (parentElement.getAttribute('id') || 'no_id_' + Math.random());
                                
                                if (!textGroups[key]) {
                                    textGroups[key] = {
                                        parent: parentElement,
                                        elements: [],
                                        isTspanGroup: isTspan
                                    };
                                }
                                
                                textGroups[key].elements.push({
                                    element: text,
                                    isTspan: isTspan
                                });
                            });
                            
                            // Position each group
                            Object.values(textGroups).forEach(group => {
                                const elements = group.elements;
                                if (elements.length === 0) return;
                                
                                // Calculate total height
                                let totalHeight = 0;
                                elements.forEach(item => {
                                    try {
                                        const bbox = item.element.getBBox();
                                        totalHeight += bbox.height || 20;
                                    } catch (e) {
                                        totalHeight += 20;
                                    }
                                });
                                
                                // Add spacing
                                totalHeight += (elements.length - 1) * 5;
                                
                                // Start position
                                const startY = boxCenterY - totalHeight / 2;
                                let currentY = startY;
                                
                                // Position each element
                                elements.forEach((item, index) => {
                                    try {
                                        const bbox = item.element.getBBox();
                                        const elementHeight = bbox.height || 20;
                                        
                                        if (item.isTspan) {
                                            // For tspan, set y attribute
                                            item.element.setAttribute('y', currentY.toString());
                                        } else {
                                            // For text element, set both x and y
                                            item.element.setAttribute('x', boxCenterX.toString());
                                            item.element.setAttribute('y', currentY.toString());
                                            // Also ensure text-anchor is middle
                                            item.element.setAttribute('text-anchor', 'middle');
                                        }
                                        
                                        currentY += elementHeight + 5;
                                    } catch (e) {
                                        console.warn('Could not position element:', item.element, e);
                                    }
                                });
                            });
                        }
                        
                        findNoteBoxes() {
                            if (!this.svg) return [];
                            const noteBoxes = [];
                            
                            const rects = this.svg.querySelectorAll('rect');
                            rects.forEach(rect => {
                                const fill = rect.getAttribute('fill') || '';
                                if (fill.includes('fffacd') || fill.includes('ffff00') || fill === 'yellow') {
                                    noteBoxes.push(rect);
                                }
                            });
                            
                            const noteGroups = this.svg.querySelectorAll('g.note, .note rect');
                            noteGroups.forEach(element => {
                                if (element.tagName === 'rect') {
                                    noteBoxes.push(element);
                                } else if (element.tagName === 'g') {
                                    const rect = element.querySelector('rect');
                                    if (rect) noteBoxes.push(rect);
                                }
                            });
                            
                            return noteBoxes;
                        }
                        
                        handleMouseDown(e) {
                            if (this.currentEdit || this.currentDrag) return;
                            
                            const target = e.target;
                            
                            if (this.isLineElement(target)) {
                                this.handleLineMouseDown(e, target);
                            }
                            else if (this.isBoxElement(target) || target.tagName === 'text' || target.tagName === 'tspan') {
                                this.handleBoxMouseDown(e, target);
                            }
                        }
                        
                        isLineElement(element) {
                            if (!element) return false;
                            const tagName = element.tagName;
                            const stroke = element.getAttribute('stroke');
                            const className = element.getAttribute('class') || '';
                            
                            return ((tagName === 'line' || tagName === 'path' || tagName === 'polyline') && 
                                    stroke && !className.includes('note'));
                        }
                        
                        handleBoxMouseDown(e, target) {
                            e.preventDefault();
                            e.stopPropagation();
                            
                            let boxElement = target;
                            if (target.tagName === 'text' || target.tagName === 'tspan') {
                                let parent = target.parentElement;
                                while (parent && !this.isBoxElement(parent)) {
                                    parent = parent.parentElement;
                                }
                                if (parent) {
                                    boxElement = parent;
                                } else {
                                    return;
                                }
                            }
                            
                            const svgCoords = this.screenToSVG(this.svg, e.clientX, e.clientY);
                            const boxData = this.getBoxData(boxElement);
                            if (!boxData) return;
                            
                            // Get text elements in the box
                            const textElements = this.findTextInBox(boxElement);
                            
                            // Check if near edge for resize
                            let dragMode = 'move';
                            const threshold = 10;
                            const clickX = svgCoords.x;
                            const clickY = svgCoords.y;
                            
                            const nearRight = Math.abs(clickX - (boxData.x + boxData.width)) < threshold;
                            const nearBottom = Math.abs(clickY - (boxData.y + boxData.height)) < threshold;
                            
                            if (nearRight && nearBottom) {
                                dragMode = 'resizeCorner';
                            } else if (nearRight) {
                                dragMode = 'resizeRight';
                            } else if (nearBottom) {
                                dragMode = 'resizeBottom';
                            }
                            
                            this.dragStartTime = Date.now();
                            this.potentialDrag = {
                                element: boxElement,
                                boxData: boxData,
                                startScreenX: e.clientX,
                                startScreenY: e.clientY,
                                startSVGX: svgCoords.x,
                                startSVGY: svgCoords.y,
                                dragMode: dragMode,
                                textElements: textElements
                            };
                            
                            boxData.element.style.stroke = '#ff6b6b';
                            boxData.element.style.strokeWidth = '3';
                        }
                        
                        handleLineMouseDown(e, target) {
                            e.preventDefault();
                            e.stopPropagation();
                            
                            const svgCoords = this.screenToSVG(this.svg, e.clientX, e.clientY);
                            
                            this.dragStartTime = Date.now();
                            this.potentialDrag = {
                                element: target,
                                startScreenX: e.clientX,
                                startScreenY: e.clientY,
                                startSVGX: svgCoords.x,
                                startSVGY: svgCoords.y,
                                isLine: true
                            };
                            
                            target.style.stroke = '#ff6b6b';
                            target.style.strokeWidth = '3';
                        }
                        
                        handleMouseMove(e) {
                            if (this.potentialDrag && !this.currentDrag) {
                                const timeElapsed = Date.now() - this.dragStartTime;
                                const dx = e.clientX - this.potentialDrag.startScreenX;
                                const dy = e.clientY - this.potentialDrag.startScreenY;
                                const distance = Math.sqrt(dx * dx + dy * dy);
                                
                                if (timeElapsed > this.dragThreshold || distance > 3) {
                                    this.startDrag(e);
                                }
                            } else if (this.currentDrag) {
                                this.updateDrag(e);
                            }
                        }
                        
                        startDrag(e) {
                            const svgCoords = this.screenToSVG(this.svg, e.clientX, e.clientY);
                            
                            this.currentDrag = {
                                ...this.potentialDrag,
                                currentSVGX: svgCoords.x,
                                currentSVGY: svgCoords.y
                            };
                            
                            if (this.currentDrag.isLine) {
                                this.currentDrag.element.style.stroke = '#4299e1';
                                this.currentDrag.element.style.strokeWidth = '4';
                                this.currentDrag.element.style.strokeDasharray = '5,5';
                            } else {
                                this.currentDrag.boxData.element.style.stroke = '#4299e1';
                                this.currentDrag.boxData.element.style.strokeWidth = '3';
                            }
                            
                            this.createDragIndicator();
                            this.potentialDrag = null;
                        }
                        
                        updateDrag(e) {
                            if (!this.currentDrag) return;
                            
                            const svgCoords = this.screenToSVG(this.svg, e.clientX, e.clientY);
                            const dxSVG = svgCoords.x - this.currentDrag.currentSVGX;
                            const dySVG = svgCoords.y - this.currentDrag.currentSVGY;
                            
                            this.currentDrag.currentSVGX = svgCoords.x;
                            this.currentDrag.currentSVGY = svgCoords.y;
                            
                            if (this.currentDrag.isLine) {
                                this.updateLinePosition(this.currentDrag.element, dxSVG, dySVG);
                            } else {
                                this.updateBoxPosition(dxSVG, dySVG);
                            }
                            
                            if (this.dragIndicator) {
                                const dxScreen = e.clientX - this.currentDrag.startScreenX;
                                const dyScreen = e.clientY - this.currentDrag.startScreenY;
                                this.dragIndicator.textContent = 'Δx: ' + dxScreen.toFixed(0) + ', Δy: ' + dyScreen.toFixed(0);
                                this.dragIndicator.style.left = (e.clientX + 15) + 'px';
                                this.dragIndicator.style.top = (e.clientY + 15) + 'px';
                            }
                        }
                        
                        updateBoxPosition(dxSVG, dySVG) {
                            const boxData = this.currentDrag.boxData;
                            if (!boxData) return;
                            
                            const rect = boxData.element;
                            const dragMode = this.currentDrag.dragMode;
                            
                            switch(dragMode) {
                                case 'move':
                                    // Move the box
                                    const newX = boxData.x + dxSVG;
                                    const newY = boxData.y + dySVG;
                                    rect.setAttribute('x', newX.toString());
                                    rect.setAttribute('y', newY.toString());
                                    
                                    // Update box data
                                    boxData.x = newX;
                                    boxData.y = newY;
                                    
                                    // Move text elements with the box
                                    if (this.currentDrag.textElements) {
                                        this.currentDrag.textElements.forEach(text => {
                                            try {
                                                const textX = parseFloat(text.getAttribute('x') || 0);
                                                const textY = parseFloat(text.getAttribute('y') || 0);
                                                const relX = textX - (boxData.x - dxSVG);
                                                const relY = textY - (boxData.y - dySVG);
                                                const newTextX = boxData.x + relX;
                                                const newTextY = boxData.y + relY;
                                                
                                                text.setAttribute('x', newTextX.toString());
                                                text.setAttribute('y', newTextY.toString());
                                            } catch (e) {
                                                // Skip if we can't move this text
                                            }
                                        });
                                    }
                                    break;
                                    
                                case 'resizeRight':
                                    const newWidth = Math.max(100, boxData.width + dxSVG);
                                    rect.setAttribute('width', newWidth.toString());
                                    boxData.width = newWidth;
                                    // Center text after resize
                                    this.centerTextInBox(this.currentDrag.element, this.currentDrag.textElements);
                                    break;
                                    
                                case 'resizeBottom':
                                    const newHeight = Math.max(60, boxData.height + dySVG);
                                    rect.setAttribute('height', newHeight.toString());
                                    boxData.height = newHeight;
                                    // Center text after resize
                                    this.centerTextInBox(this.currentDrag.element, this.currentDrag.textElements);
                                    break;
                                    
                                case 'resizeCorner':
                                    const newWidthCorner = Math.max(100, boxData.width + dxSVG);
                                    const newHeightCorner = Math.max(60, boxData.height + dySVG);
                                    rect.setAttribute('width', newWidthCorner.toString());
                                    rect.setAttribute('height', newHeightCorner.toString());
                                    boxData.width = newWidthCorner;
                                    boxData.height = newHeightCorner;
                                    // Center text after resize
                                    this.centerTextInBox(this.currentDrag.element, this.currentDrag.textElements);
                                    break;
                            }
                        }
                        
                        updateLinePosition(element, dxSVG, dySVG) {
                            if (element.tagName === 'line') {
                                const x1 = parseFloat(element.getAttribute('x1') || 0);
                                const y1 = parseFloat(element.getAttribute('y1') || 0);
                                const x2 = parseFloat(element.getAttribute('x2') || 0);
                                const y2 = parseFloat(element.getAttribute('y2') || 0);
                                
                                element.setAttribute('x1', (x1 + dxSVG).toString());
                                element.setAttribute('y1', (y1 + dxSVG).toString());
                                element.setAttribute('x2', (x2 + dxSVG).toString());
                                element.setAttribute('y2', (y2 + dxSVG).toString());
                            }
                        }
                        
                        handleMouseUp(e) {
                            if (this.currentDrag) {
                                this.finishDrag(e);
                            } else if (this.potentialDrag) {
                                this.cancelDrag();
                            }
                        }
                        
                        finishDrag(e) {
                            if (!this.currentDrag) return;
                            
                            const svgCoords = this.screenToSVG(this.svg, e.clientX, e.clientY);
                            const dxSVG = svgCoords.x - this.currentDrag.currentSVGX;
                            const dySVG = svgCoords.y - this.currentDrag.currentSVGY;
                            
                            if (this.currentDrag.isLine) {
                                this.updateLinePosition(this.currentDrag.element, dxSVG, dySVG);
                            } else {
                                this.updateBoxPosition(dxSVG, dySVG);
                            }
                            
                            if (this.currentDrag.isLine) {
                                this.currentDrag.element.style.stroke = '';
                                this.currentDrag.element.style.strokeWidth = '';
                                this.currentDrag.element.style.strokeDasharray = '';
                            } else {
                                this.currentDrag.boxData.element.style.stroke = '';
                                this.currentDrag.boxData.element.style.strokeWidth = '';
                            }
                            
                            this.removeDragIndicator();
                            this.showDragSuccess(e);
                            this.currentDrag = null;
                        }
                        
                        cancelDrag() {
                            if (this.potentialDrag) {
                                if (this.potentialDrag.isLine) {
                                    this.potentialDrag.element.style.stroke = '';
                                    this.potentialDrag.element.style.strokeWidth = '';
                                } else if (this.potentialDrag.boxData) {
                                    this.potentialDrag.boxData.element.style.stroke = '';
                                    this.potentialDrag.boxData.element.style.strokeWidth = '';
                                }
                            }
                            this.potentialDrag = null;
                            this.currentDrag = null;
                            this.removeDragIndicator();
                        }
                        
                        createDragIndicator() {
                            this.removeDragIndicator();
                            
                            const indicator = document.createElement('div');
                            indicator.id = 'drag-indicator';
                            indicator.style.position = 'fixed';
                            indicator.style.left = '10px';
                            indicator.style.top = '10px';
                            indicator.style.backgroundColor = 'rgba(66, 153, 225, 0.9)';
                            indicator.style.color = 'white';
                            indicator.style.padding = '5px 10px';
                            indicator.style.borderRadius = '4px';
                            indicator.style.fontSize = '12px';
                            indicator.style.fontFamily = 'monospace';
                            indicator.style.zIndex = '10001';
                            indicator.style.pointerEvents = 'none';
                            indicator.textContent = 'Dragging...';
                            
                            document.body.appendChild(indicator);
                            this.dragIndicator = indicator;
                        }
                        
                        removeDragIndicator() {
                            if (this.dragIndicator && this.dragIndicator.parentElement) {
                                this.dragIndicator.parentElement.removeChild(this.dragIndicator);
                            }
                            this.dragIndicator = null;
                        }
                        
                        showDragSuccess(e) {
                            const dxScreen = e.clientX - this.currentDrag.startScreenX;
                            const dyScreen = e.clientY - this.currentDrag.startScreenY;
                            
                            const success = document.createElement('div');
                            success.style.position = 'fixed';
                            success.style.left = '50%';
                            success.style.top = '20px';
                            success.style.transform = 'translateX(-50%)';
                            success.style.backgroundColor = 'rgba(72, 187, 120, 0.9)';
                            success.style.color = 'white';
                            success.style.padding = '8px 16px';
                            success.style.borderRadius = '4px';
                            success.style.fontSize = '14px';
                            success.style.zIndex = '10001';
                            success.style.boxShadow = '0 2px 8px rgba(0,0,0,0.2)';
                            success.textContent = 'Element adjusted: Δx=' + dxScreen.toFixed(0) + ', Δy=' + dyScreen.toFixed(0);
                            
                            document.body.appendChild(success);
                            
                            setTimeout(() => {
                                if (success.parentElement) {
                                    success.parentElement.removeChild(success);
                                }
                            }, 2000);
                        }
                        
                        setupHoverEffects() {
                            if (!this.svg) return;
                            
                            this.svg.addEventListener('mouseover', (e) => {
                                const target = e.target;
                                if (target.tagName === 'text' || target.tagName === 'tspan') {
                                    target.style.cursor = 'text';
                                    target.style.textShadow = '0 0 2px rgba(59, 130, 246, 0.5)';
                                } else if (this.isLineElement(target)) {
                                    target.style.cursor = 'move';
                                    target.style.strokeWidth = '3';
                                } else if (this.isBoxElement(target)) {
                                    const rect = target.tagName === 'rect' ? target : target.querySelector('rect');
                                    if (rect) {
                                        rect.style.cursor = 'move';
                                        rect.style.strokeWidth = '2';
                                    }
                                }
                            });
                            
                            this.svg.addEventListener('mouseout', (e) => {
                                const target = e.target;
                                if (target.tagName === 'text' || target.tagName === 'tspan') {
                                    target.style.textShadow = '';
                                } else if (this.isLineElement(target) && !this.currentDrag) {
                                    target.style.strokeWidth = '';
                                } else if (this.isBoxElement(target) && !this.currentDrag) {
                                    const rect = target.tagName === 'rect' ? target : target.querySelector('rect');
                                    if (rect) {
                                        rect.style.strokeWidth = '';
                                    }
                                }
                            });
                        }
                        
                        handleDoubleClick(event, svg) {
                            if (this.currentEdit || this.currentDrag) {
                                if (this.currentEdit) this.cancelEdit();
                                if (this.currentDrag) this.cancelDrag();
                                return;
                            }
                            
                            event.preventDefault();
                            event.stopPropagation();
                            
                            const target = event.target;
                            let textElement = target.tagName === 'tspan' ? target.parentElement : target;
                            
                            if (textElement.tagName !== 'text') return;
                            
                            const currentText = this.getTextContent(textElement);
                            if (!currentText.trim()) return;
                            
                            const originalFill = textElement.getAttribute('fill') || '#333333';
                            this.createEditInput(textElement, currentText, originalFill, svg);
                        }
                        
                        getTextContent(element) {
                            const tspans = element.querySelectorAll('tspan');
                            if (tspans.length > 0) {
                                return Array.from(tspans).map(t => t.textContent).join('\n');
                            }
                            return element.textContent || '';
                        }
                        
                        createEditInput(textElement, currentText, originalFill, svg) {
                            const rect = textElement.getBoundingClientRect();
                            
                            const input = document.createElement('input');
                            input.type = 'text';
                            input.value = currentText;
                            input.style.position = 'fixed';
                            input.style.left = (rect.left + window.scrollX) + 'px';
                            input.style.top = (rect.top + window.scrollY) + 'px';
                            input.style.width = Math.max(rect.width + 20, 150) + 'px';
                            input.style.height = rect.height + 10 + 'px';
                            input.style.zIndex = '10000';
                            input.style.padding = '4px 8px';
                            input.style.border = '2px solid #4299e1';
                            input.style.borderRadius = '4px';
                            input.style.fontSize = window.getComputedStyle(textElement).fontSize;
                            input.style.fontFamily = window.getComputedStyle(textElement).fontFamily;
                            input.style.fontWeight = window.getComputedStyle(textElement).fontWeight;
                            input.style.color = '#000000';
                            input.style.backgroundColor = '#ffffff';
                            input.style.boxShadow = '0 4px 12px rgba(0, 0, 0, 0.15)';
                            
                            document.body.appendChild(input);
                            this.currentEdit = {input: input, textElement: textElement, originalFill: originalFill};
                            
                            input.focus();
                            input.select();
                            
                            const handleKeyDown = (e) => this.handleKeyDown(e);
                            const handleBlur = () => {
                                this.finishEdit(true);
                                input.removeEventListener('keydown', handleKeyDown);
                                input.removeEventListener('blur', handleBlur);
                            };
                            
                            input.addEventListener('keydown', handleKeyDown);
                            input.addEventListener('blur', handleBlur);
                        }
                        
                        handleKeyDown(event) {
                            if (!this.currentEdit) return;
                            
                            switch(event.key) {
                                case 'Enter':
                                    event.preventDefault();
                                    this.finishEdit(true);
                                    break;
                                case 'Escape':
                                    event.preventDefault();
                                    this.cancelEdit();
                                    break;
                            }
                        }
                        
                        finishEdit(saveChanges) {
                            if (!this.currentEdit) return;
                            
                            const {input, textElement, originalFill} = this.currentEdit;
                            const newText = input.value.trim();
                            const currentText = this.getTextContent(textElement);
                            
                            if (input && input.parentElement) {
                                try {
                                    input.parentElement.removeChild(input);
                                } catch (e) {
                                    console.warn('Could not remove input:', e);
                                }
                            }
                            
                            if (saveChanges && newText && newText !== currentText) {
                                this.updateTextElement(textElement, newText);
                                textElement.setAttribute('fill', originalFill);
                                
                                // Find the box containing this text and re-center
                                const boxes = this.findAllBoxes();
                                boxes.forEach(box => {
                                    const texts = this.findTextInBox(box);
                                    if (texts.includes(textElement)) {
                                        this.centerTextInBox(box, texts);
                                    }
                                });
                                
                                // Notify Python if bridge exists
                                if (window.qtBridge && window.qtBridge.onElementEdited) {
                                    const rect = textElement.getBoundingClientRect();
                                    window.qtBridge.onElementEdited(
                                        'element_' + Date.now(),
                                        'text',
                                        newText,
                                        rect.left,
                                        rect.top
                                    );
                                }
                            } else {
                                textElement.setAttribute('fill', originalFill);
                            }
                            
                            this.currentEdit = null;
                        }
                        
                        cancelEdit() {
                            if (!this.currentEdit) return;
                            
                            const {input, textElement, originalFill} = this.currentEdit;
                            
                            if (input && input.parentElement) {
                                try {
                                    input.parentElement.removeChild(input);
                                } catch (e) {
                                    console.warn('Could not remove input:', e);
                                }
                            }
                            
                            textElement.setAttribute('fill', originalFill);
                            this.currentEdit = null;
                        }
                        
                        updateTextElement(textElement, newText) {
                            const tspans = textElement.querySelectorAll('tspan');
                            
                            if (tspans.length > 0) {
                                const lines = newText.split('\n');
                                tspans.forEach((tspan, index) => {
                                    if (index < lines.length) {
                                        tspan.textContent = lines[index];
                                    }
                                });
                                
                                if (lines.length > tspans.length) {
                                    for (let i = tspans.length; i < lines.length; i++) {
                                        const newTspan = document.createElementNS('http://www.w3.org/2000/svg', 'tspan');
                                        newTspan.textContent = lines[i];
                                        newTspan.setAttribute('x', tspans[0].getAttribute('x') || '0');
                                        newTspan.setAttribute('dy', '1.2em');
                                        textElement.appendChild(newTspan);
                                    }
                                }
                            } else {
                                textElement.textContent = newText;
                            }
                        }
                    }

                    // Initialize the editor when the page loads
                    document.addEventListener('DOMContentLoaded', function() {
                        console.log('DOM loaded, initializing editor');
                        setTimeout(() => {
                            window.mermaidEditor = new EnhancedMermaidEditor();
                            console.log('Mermaid editor initialized');
                        }, 1500);
                    });
                </script>
                <style>
                    .mermaid svg text,
                    .mermaid svg tspan {
                        fill: #333333 !important;
                        color: #333333 !important;
                        user-select: none;
                        pointer-events: auto;
                    }

                    .mermaid svg line:hover,
                    .mermaid svg path:hover,
                    .mermaid svg polyline:hover {
                        stroke-width: 3px !important;
                        cursor: move !important;
                        stroke: #4299e1 !important;
                    }

                    .mermaid svg rect[fill*="fff7ed"]:hover,
                    .mermaid svg rect[fill*="f0fdf4"]:hover,
                    .mermaid svg rect[fill*="eef2ff"]:hover,
                    .mermaid svg rect[fill*="fffacd"]:hover,
                    .mermaid svg .note rect:hover {
                        stroke-width: 3px !important;
                        stroke: #4299e1 !important;
                        cursor: move !important;
                        filter: drop-shadow(0 0 3px rgba(66, 153, 225, 0.3));
                    }

                    .mermaid svg .dragging-box,
                    .mermaid svg rect.dragging {
                        stroke-width: 3px !important;
                        stroke-dasharray: 5,3 !important;
                        stroke: #4299e1 !important;
                        filter: drop-shadow(0 0 5px rgba(66, 153, 225, 0.5));
                        animation: pulse-box 1.5s infinite;
                    }

                    .mermaid svg .dragging-text,
                    .mermaid svg text.dragging {
                        fill: #2c5282 !important;
                        font-weight: bold !important;
                        filter: drop-shadow(0 0 2px rgba(66, 153, 225, 0.3));
                    }

                    .mermaid svg .dragging-line,
                    .mermaid svg line.dragging,
                    .mermaid svg path.dragging {
                        stroke-width: 4px !important;
                        stroke-dasharray: 5,5 !important;
                        stroke: #4299e1 !important;
                        animation: pulse-line 1.5s infinite;
                    }

                    @keyframes pulse-box {
                        0% { stroke-opacity: 0.7; }
                        50% { stroke-opacity: 1; }
                        100% { stroke-opacity: 0.7; }
                    }

                    @keyframes pulse-line {
                        0% { stroke-dashoffset: 10; }
                        100% { stroke-dashoffset: 0; }
                    }

                    #drag-indicator {
                        font-family: 'Courier New', monospace;
                        font-weight: bold;
                        box-shadow: 0 2px 8px rgba(0,0,0,0.3);
                        background: linear-gradient(135deg, #4299e1, #3182ce) !important;
                        color: white !important;
                        padding: 8px 12px !important;
                        border-radius: 6px !important;
                        font-size: 13px !important;
                        border: 2px solid #ffffff !important;
                        z-index: 10001 !important;
                    }

                    input.mermaid-edit {
                        position: fixed !important;
                        z-index: 10000 !important;
                        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.25) !important;
                        border: 3px solid #4299e1 !important;
                        border-radius: 8px !important;
                        font-size: 14px !important;
                        background: #ffffff !important;
                        color: #000000 !important;
                        transition: all 0.2s ease !important;
                    }

                    input.mermaid-edit:focus {
                        outline: none !important;
                        box-shadow: 0 4px 25px rgba(66, 153, 225, 0.4) !important;
                        border-color: #3182ce !important;
                    }

                    .mermaid svg rect[fill*="fff7ed"],
                    .mermaid svg rect[fill*="f0fdf4"],
                    .mermaid svg rect[fill*="eef2ff"],
                    .mermaid svg rect[fill*="fffacd"] {
                        stroke: #cbd5e1 !important;
                        stroke-width: 2px !important;
                        rx: 8px !important;
                        ry: 8px !important;
                        transition: all 0.2s ease !important;
                    }

                    .mermaid svg text {
                        text-anchor: middle !important;
                        dominant-baseline: middle !important;
                        font-family: 'Segoe UI', 'Arial', sans-serif !important;
                        transition: fill 0.2s ease !important;
                    }

                    .mermaid svg rect[fill*="fff7ed"],
                    .mermaid svg rect[fill*="f0fdf4"],
                    .mermaid svg rect[fill*="eef2ff"],
                    .mermaid svg rect[fill*="fffacd"] {
                        filter: drop-shadow(0 2px 4px rgba(0, 0, 0, 0.1));
                    }

                    .mermaid svg rect[fill*="fff7ed"]:hover,
                    .mermaid svg rect[fill*="f0fdf4"]:hover,
                    .mermaid svg rect[fill*="eef2ff"]:hover,
                    .mermaid svg rect[fill*="fffacd"]:hover {
                        filter: drop-shadow(0 0 8px rgba(66, 153, 225, 0.3)) !important;
                    }

                    .mermaid svg .note rect {
                        stroke: #ecc94b !important;
                        stroke-width: 2px !important;
                        filter: drop-shadow(0 2px 4px rgba(236, 201, 75, 0.2));
                        transition: all 0.2s ease !important;
                    }

                    .mermaid svg .note rect:hover {
                        stroke-width: 3px !important;
                        stroke: #d69e2e !important;
                        filter: drop-shadow(0 0 8px rgba(236, 201, 75, 0.3)) !important;
                    }

                    .mermaid svg .note text {
                        fill: #744210 !important;
                        text-anchor: middle !important;
                        dominant-baseline: middle !important;
                        pointer-events: auto !important;
                    }

                    .mermaid svg .messageLine0,
                    .mermaid svg .messageLine1 {
                        stroke-width: 2px !important;
                        transition: all 0.2s ease !important;
                    }

                    .mermaid svg .messageLine0:hover,
                    .mermaid svg .messageLine1:hover {
                        stroke-width: 4px !important;
                        stroke: #4299e1 !important;
                    }

                    .mermaid svg .messageText {
                        fill: #4a5568 !important;
                        font-weight: 500 !important;
                    }

                    .mermaid svg .active-drag {
                        cursor: grabbing !important;
                    }
                </style>
            """
            
            html_template = f'''<!DOCTYPE html>
            <html lang="en">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>{title}</title>
                <script type="module">
                    import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs';
                    mermaid.initialize({{
                        startOnLoad: true,
                        theme: 'base',
                        themeVariables: {{
                            primaryColor: '#e0e7ff',
                            edgeLabelBackground: '#ffffff',
                            tertiaryColor: '#f0fdf4',
                            primaryTextColor: '#333333',
                            secondaryTextColor: '#333333',
                            tertiaryTextColor: '#333333',
                            noteTextColor: '#333333',
                            noteBkgColor: '#fffacd',
                            actorBkgColor: '#e0e7ff',
                            actorBorderColor: '#a5b4fc',
                            actorTextColor: '#333333',
                            labelBoxBkgColor: '#f0fdf4',
                            labelBoxBorderColor: '#86efac',
                            labelTextColor: '#333333',
                            fontFamily: 'Arial, sans-serif',
                            fontSize: '16px'
                        }}
                    }});
                </script>
                {editing_js if enable_editing else ''}
                <style>
                    body {{
                        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
                        background-color: #f9fafb;
                        margin: 0;
                        padding: 20px;
                        overflow-x: hidden;
                    }}
                    
                    .container {{
                        max-width: 1200px;
                        margin: 0 auto;
                        background: white;
                        border-radius: 12px;
                        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
                        padding: 24px;
                        position: relative;
                    }}
                    
                    .header {{
                        text-align: center;
                        margin-bottom: 24px;
                        position: relative;
                    }}
                    
                    .header h1 {{
                        font-size: 28px;
                        font-weight: bold;
                        color: #1f2937;
                        margin-bottom: 8px;
                        text-shadow: 0 1px 2px rgba(0, 0, 0, 0.05);
                    }}
                    
                    .header p {{
                        color: #6b7280;
                        font-size: 14px;
                    }}
                    
                    .voltage-info {{
                        display: inline-block;
                        background: linear-gradient(135deg, #e0e7ff, #c7d2fe);
                        padding: 6px 16px;
                        border-radius: 20px;
                        font-size: 12px;
                        font-weight: 600;
                        color: #4f46e5;
                        margin-left: 10px;
                        border: 1px solid #c7d2fe;
                        box-shadow: 0 1px 3px rgba(199, 210, 254, 0.5);
                    }}
                    
                    .key-box {{
                        margin-top: 24px;
                        padding-top: 16px;
                        border-top: 1px solid #e5e7eb;
                        display: grid;
                        grid-template-columns: 1fr;
                        gap: 16px;
                        background: #f9fafb;
                        border-radius: 8px;
                        padding: 16px;
                    }}
                    
                    @media (min-width: 768px) {{
                        .key-box {{
                            grid-template-columns: repeat(3, 1fr);
                        }}
                    }}
                    
                    .key-section {{
                        padding: 16px;
                        background: white;
                        border-radius: 8px;
                        border: 1px solid #e5e7eb;
                        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
                        transition: all 0.2s ease;
                    }}
                    
                    .key-section:hover {{
                        transform: translateY(-2px);
                        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.07);
                        border-color: #cbd5e1;
                    }}
                    
                    .key-section strong {{
                        display: block;
                        margin-bottom: 12px;
                        font-size: 14px;
                        font-weight: 700;
                    }}
                    
                    .key-section ul {{
                        list-style-type: disc;
                        padding-left: 20px;
                        margin: 0;
                    }}
                    
                    .key-section li {{
                        margin-bottom: 6px;
                        font-size: 13px;
                        color: #4b5563;
                        line-height: 1.5;
                    }}
                    
                    .blue-text {{
                        color: #1d4ed8;
                        background: linear-gradient(135deg, #1d4ed8, #3b82f6);
                        -webkit-background-clip: text;
                        -webkit-text-fill-color: transparent;
                        background-clip: text;
                    }}
                    
                    .green-text {{
                        color: #047857;
                        background: linear-gradient(135deg, #047857, #10b981);
                        -webkit-background-clip: text;
                        -webkit-text-fill-color: transparent;
                        background-clip: text;
                    }}
                    
                    .orange-text {{
                        color: #ea580c;
                        background: linear-gradient(135deg, #ea580c, #f97316);
                        -webkit-background-clip: text;
                        -webkit-text-fill-color: transparent;
                        background-clip: text;
                    }}
                    
                    .language-badge {{
                        position: absolute;
                        top: 10px;
                        right: 10px;
                        background: linear-gradient(135deg, #3b82f6, #1d4ed8);
                        color: white;
                        padding: 6px 12px;
                        border-radius: 6px;
                        font-size: 12px;
                        font-weight: 600;
                        box-shadow: 0 2px 4px rgba(59, 130, 246, 0.3);
                        border: 1px solid #3b82f6;
                    }}
                    
                    .language-badge[data-lang="ja"] {{
                        background: linear-gradient(135deg, #ef4444, #dc2626);
                        border-color: #ef4444;
                    }}
                    
                    .edit-hint {{
                        background: linear-gradient(135deg, #fef3c7, #fde68a);
                        border: 1px solid #fbbf24;
                        border-radius: 8px;
                        padding: 12px 16px;
                        margin-top: 16px;
                        font-size: 13px;
                        color: #92400e;
                        text-align: center;
                        font-weight: 500;
                        box-shadow: 0 2px 4px rgba(251, 191, 36, 0.2);
                    }}
                    
                    .mermaid svg text {{
                        fill: #333333 !important;
                    }}
                    
                    .mermaid svg tspan {{
                        fill: #333333 !important;
                    }}
                    
                    .mermaid svg .actor text {{
                        fill: #333333 !important;
                        font-weight: bold;
                    }}
                    
                    .mermaid svg .note text {{
                        fill: #333333 !important;
                    }}
                    
                    .mermaid svg .messageText {{
                        fill: #333333 !important;
                        font-weight: 500;
                    }}
                    
                    .mermaid svg .label text {{
                        fill: #333333 !important;
                    }}
                    
                    .mermaid {{
                        width: 100%;
                        overflow: auto;
                        background: #f8fafc;
                        border-radius: 8px;
                        padding: 16px;
                        border: 1px solid #e5e7eb;
                        margin-bottom: 20px;
                    }}
                    
                    .mermaid svg {{
                        width: 100% !important;
                        height: auto !important;
                        max-width: 100%;
                        background: white;
                        border-radius: 4px;
                        padding: 10px;
                    }}
                    
                    @media (max-width: 768px) {{
                        body {{
                            padding: 10px;
                        }}
                        
                        .container {{
                            padding: 16px;
                            border-radius: 8px;
                        }}
                        
                        .header h1 {{
                            font-size: 22px;
                        }}
                        
                        .mermaid {{
                            padding: 8px;
                        }}
                        
                        .key-box {{
                            grid-template-columns: 1fr;
                            gap: 12px;
                            padding: 12px;
                        }}
                    }}
                </style>
            </head>
            <body>

                <div class="container">
                    <div class="language-badge" data-lang="{language}">{'English' if language == 'en' else '日本語'}</div> 
                    
                    <div class="header">
                        <h1>{title}</h1>
                        <p>{key['generated']} <span class="voltage-info">Voltage: {voltage}</span></p>
                        <div class="edit-hint">{key['tip']}</div>
                    </div>

                    <div class="mermaid">
            {mermaid_code}
                    </div>
                    
                    <div class="key-box">
                        <div class="key-section">
                            <strong class="blue-text">{key['logic_title']}</strong>
                            <ul>
                                <li>{key['logic_items'][0]}</li>
                                <li>{key['logic_items'][1]}</li>
                                <li>{key['logic_items'][2]}</li>
                            </ul>
                        </div>
                        <div class="key-section">
                            <strong class="green-text">{key['safety_title']}</strong>
                            <ul>
                                <li>{key['safety_items'][0]}</li>
                                <li>{key['safety_items'][1]}</li>
                                <li>{key['safety_items'][2]}</li>
                            </ul>
                        </div>
                        <div class="key-section">
                            <strong class="orange-text">{key['components_title']}</strong>
                            <ul>
                                <li>{key['components_items'][0]}</li>
                                <li>{key['components_items'][1]}</li>
                                <li>{key['components_items'][2]}</li>
                            </ul>
                        </div>
                    </div>
                </div>

            </body>
            </html>'''
            
            return html_template