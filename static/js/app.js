// Chatbot Frontend - Vanilla JavaScript (ES6+)
// State management and UI controller for chatbot interface

class ChatbotApp {
    constructor() {
        this.state = {
            currentChatId: null,
            chats: [],
            isProcessing: false,
            currentTask: null,
            apiConfig: {
                deepseek: null,
                elevenlabs: null,
                pixabay: null,
                survey: null
            }
        };
        
        this.init();
    }

    // Initialize application
    init() {
        this.cacheDOM();
        this.bindEvents();
        this.loadChatHistory();
        this.loadAPIConfig();
    }

    // Cache DOM elements
    cacheDOM() {
        this.elements = {
            chatWindow: document.getElementById('chatWindow'),
            messageInput: document.getElementById('messageInput'),
            sendButton: document.getElementById('sendButton'),
            newChatBtn: document.getElementById('newChatBtn'),
            chatHistory: document.getElementById('chatHistory'),
            taskSidebar: document.getElementById('taskSidebar'),
            voiceToggle: document.getElementById('voiceToggle'),
            languageSelect: document.getElementById('languageSelect'),
            processingIndicator: document.getElementById('processingIndicator'),
            errorContainer: document.getElementById('errorContainer')
        };
    }

    // Bind event listeners using event delegation
    bindEvents() {
        // Send message on button click or Enter key
        this.elements.sendButton.addEventListener('click', () => this.sendMessage());
        this.elements.messageInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });

        // New chat button
        this.elements.newChatBtn.addEventListener('click', () => this.createNewChat());

        // Voice toggle
        this.elements.voiceToggle.addEventListener('change', (e) => {
            this.state.useVoice = e.target.checked;
            this.savePreference('useVoice', e.target.checked);
        });

        // Language selection
        this.elements.languageSelect.addEventListener('change', (e) => {
            this.state.currentLanguage = e.target.value;
            this.savePreference('language', e.target.value);
        });

        // Chat history delegation
        this.elements.chatHistory.addEventListener('click', (e) => {
            const chatItem = e.target.closest('.chat-history-item');
            if (chatItem) {
                const chatId = chatItem.dataset.chatId;
                this.loadChat(chatId);
            }
        });
    }

    // Create new chat session
    createNewChat() {
        const chatId = 'chat_' + Date.now();
        const newChat = {
            id: chatId,
            title: 'New Chat ' + new Date().toLocaleTimeString(),
            messages: [],
            createdAt: new Date().toISOString()
        };

        this.state.chats.unshift(newChat);
        this.state.currentChatId = chatId;
        
        this.updateChatHistory();
        this.clearChatWindow();
        this.saveChatHistory();
        
        this.elements.messageInput.focus();
    }

    // Load specific chat
    loadChat(chatId) {
        const chat = this.state.chats.find(c => c.id === chatId);
        if (!chat) return;

        this.state.currentChatId = chatId;
        this.clearChatWindow();
        
        chat.messages.forEach(message => {
            this.appendMessage(message);
        });
        
        this.elements.messageInput.focus();
    }

    // Send message to backend
    async sendMessage() {
        const messageText = this.elements.messageInput.value.trim();
        if (!messageText || this.state.isProcessing) return;

        // Create user message
        const userMessage = {
            id: 'msg_' + Date.now(),
            type: 'user',
            content: messageText,
            timestamp: new Date().toISOString(),
            language: this.state.currentLanguage || 'auto'
        };

        // Append to UI
        this.appendMessage(userMessage);
        this.elements.messageInput.value = '';
        
        // Add to current chat
        const currentChat = this.state.chats.find(c => c.id === this.state.currentChatId);
        if (currentChat) {
            currentChat.messages.push(userMessage);
            currentChat.updatedAt = new Date().toISOString();
        }

        // Show processing indicator
        this.setProcessingState(true);

        try {
            // Send to backend API
            const response = await this.callBackendAPI({
                type: 'chat',
                message: messageText,
                language: this.state.currentLanguage,
                useVoice: this.state.useVoice,
                chatId: this.state.currentChatId
            });

            // Create bot message
            const botMessage = {
                id: 'msg_' + Date.now(),
                type: 'bot',
                content: response.text || response.message,
                timestamp: new Date().toISOString(),
                metadata: response.metadata || {}
            };

            // Append bot response
            this.appendMessage(botMessage);

            // Add to current chat
            if (currentChat) {
                currentChat.messages.push(botMessage);
            }

            // Handle multimedia if present
            if (response.media) {
                await this.handleMediaResponse(response.media);
            }

            // Handle voice if enabled
            if (this.state.useVoice && response.audio) {
                await this.playAudio(response.audio);
            }

            // Save chat history
            this.saveChatHistory();
            this.updateChatHistory();

        } catch (error) {
            this.showError('Failed to get response: ' + error.message);
            console.error('API Error:', error);
        } finally {
            this.setProcessingState(false);
        }
    }

    // Call backend API
    async callBackendAPI(payload) {
        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(payload)
        });

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        return await response.json();
    }

    // Handle media responses (images/videos)
    async handleMediaResponse(media) {
        if (media.images && media.images.length > 0) {
            media.images.forEach(img => {
                this.appendMedia('image', img.url, img.caption);
            });
        }

        if (media.videos && media.videos.length > 0) {
            media.videos.forEach(vid => {
                this.appendMedia('video', vid.url, vid.caption);
            });
        }
    }

    // Play audio from ElevenLabs
    async playAudio(audioData) {
        try {
            const audio = new Audio(`data:audio/mp3;base64,${audioData}`);
            await audio.play();
        } catch (error) {
            console.warn('Audio playback failed:', error);
        }
    }

    // Append message to chat window
    appendMessage(message) {
        const messageElement = this.createMessageElement(message);
        this.elements.chatWindow.appendChild(messageElement);
        this.scrollToBottom();
    }

    // Append media to chat window
    appendMedia(type, url, caption) {
        const mediaContainer = document.createElement('div');
        mediaContainer.className = 'media-container';
        
        let mediaElement;
        if (type === 'image') {
            mediaElement = document.createElement('img');
            mediaElement.src = url;
            mediaElement.alt = caption || 'Image';
        } else if (type === 'video') {
            mediaElement = document.createElement('video');
            mediaElement.src = url;
            mediaElement.controls = true;
        }
        
        mediaElement.className = 'chat-media';
        mediaContainer.appendChild(mediaElement);
        
        if (caption) {
            const captionElement = document.createElement('div');
            captionElement.className = 'media-caption';
            captionElement.textContent = caption;
            mediaContainer.appendChild(captionElement);
        }
        
        this.elements.chatWindow.appendChild(mediaContainer);
        this.scrollToBottom();
    }

    // Create message element
    createMessageElement(message) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${message.type}-message`;
        messageDiv.dataset.messageId = message.id;
        
        const contentDiv = document.createElement('div');
        contentDiv.className = 'message-content';
        
        // Format code blocks if present
        if (message.type === 'bot' && message.content.includes('')) {
            contentDiv.innerHTML = this.formatCodeBlocks(message.content);
        } else {
            contentDiv.textContent = message.content;
        }
        
        const timeDiv = document.createElement('div');
        timeDiv.className = 'message-time';
        timeDiv.textContent = new Date(message.timestamp).toLocaleTimeString();
        
        messageDiv.appendChild(contentDiv);
        messageDiv.appendChild(timeDiv);
        
        return messageDiv;
    }

    // Format code blocks with syntax highlighting
    formatCodeBlocks(text) {
        return text.replace(/(\w+)?\n([\s\S]*?)/g, (match, lang, code) => {
            const language = lang || 'text';
            return `<pre class="code-block"><code class="language-${language}">${this.escapeHtml(code.trim())}</code></pre>`;
        });
    }

    // Escape HTML for safety
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    // Update chat history sidebar
    updateChatHistory() {
        this.elements.chatHistory.innerHTML = '';
        
        this.state.chats.forEach(chat => {
            const chatItem = document.createElement('div');
            chatItem.className = `chat-history-item ${chat.id === this.state.currentChatId ? 'active' : ''}`;
            chatItem.dataset.chatId = chat.id;
            
            const title = document.createElement('div');
            title.className = 'chat-title';
            title.textContent = chat.title || 'Untitled Chat';
            
            const time = document.createElement('div');
            time.className = 'chat-time';
            time.textContent = new Date(chat.createdAt).toLocaleDateString();
            
            chatItem.appendChild(title);
            chatItem.appendChild(time);
            this.elements.chatHistory.appendChild(chatItem);
        });
    }

    // Clear chat window
    clearChatWindow() {
        this.elements.chatWindow.innerHTML = '';
    }

    // Scroll to bottom of chat
    scrollToBottom() {
        this.elements.chatWindow.scrollTop = this.elements.chatWindow.scrollHeight;
    }

    // Set processing state
    setProcessingState(isProcessing) {
        this.state.isProcessing = isProcessing;
        this.elements.processingIndicator.style.display = isProcessing ? 'block' : 'none';
        this.elements.sendButton.disabled = isProcessing;
    }

    // Show error message
    showError(message) {
        this.elements.errorContainer.textContent = message;
        this.elements.errorContainer.style.display = 'block';
        
        setTimeout(() => {
            this.elements.errorContainer.style.display = 'none';
        }, 5000);
    }

    // Load chat history from localStorage
    loadChatHistory() {
        try {
            const saved = localStorage.getItem('chatHistory');
            if (saved) {
                this.state.chats = JSON.parse(saved);
                this.updateChatHistory();
                
                // Load last active chat if exists
                const lastChatId = localStorage.getItem('lastChatId');
                if (lastChatId) {
                    this.loadChat(lastChatId);
                }
            }
        } catch (error