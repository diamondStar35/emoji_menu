# -*- coding: utf-8 -*-
from . import emoji_data_python
import wx
import globalPluginHandler
import scriptHandler
import gui
from gui import guiHelper
import addonHandler
import api
import ui
import tones
import config
addonHandler.initTranslation()

confspec = {
	"lastCategory": "string(default='All')",
}
config.conf.spec['emojiMenu'] = confspec

class EmojiDialog(wx.Dialog):
	# Translators: Title for the Emoji Menu dialog window.
	_dialog_title = _("Emoji Menu")

	def __init__(self, parent):
		self.all_emojis = sorted(emoji_data_python.emoji_data, key=lambda e: e.name)
		categories = sorted(list(set(e.category for e in self.all_emojis if e.category)))
		# Translators: The label for the category representing all emojis.
		self.categories = [_("All")] + categories
		super().__init__(parent, title=self._dialog_title)

		# Create a main sizer for the dialog contents
		mainSizer = wx.BoxSizer(wx.VERTICAL)
		sHelper = guiHelper.BoxSizerHelper(self, sizer=mainSizer)

		searchLabel = sHelper.addItem(wx.StaticText(self, label=_("&Search:")))
		self.searchCtrl = sHelper.addItem(wx.TextCtrl(self))
		self.searchCtrl.Bind(wx.EVT_TEXT, self._on_search_text_changed)

		categoryLabel = sHelper.addItem(wx.StaticText(self, label=_("Ca&tegory:")))
		self.categoryRadioBox = sHelper.addItem(wx.RadioBox(
			self,
			choices=self.categories,
			majorDimension=1,
			style=wx.RA_SPECIFY_ROWS
		))
		self.categoryRadioBox.Bind(wx.EVT_RADIOBOX, self._on_category_changed)

		emojiListLabel = sHelper.addItem(wx.StaticText(self, label=_("&Emojis:")))
		self.emojiListBox = sHelper.addItem(wx.ListBox(self, style=wx.LB_SINGLE), proportion=1, flag=wx.EXPAND)
		self.emojiListBox.Bind(wx.EVT_LISTBOX_DCLICK, self._on_emoji_selected)

		self.searchUpdateTimer = wx.Timer(self)
		self.Bind(wx.EVT_TIMER, self._perform_update_list, self.searchUpdateTimer)

		closeButton = sHelper.addItem(wx.Button(self, id=wx.ID_CLOSE))
		closeButton.Bind(wx.EVT_BUTTON, lambda evt: self.Close())

		self.SetSizer(mainSizer)
		mainSizer.Fit(self)
		self.CenterOnParent()
		self.Bind(wx.EVT_CHAR_HOOK, self.onCharHook)

		self._filtered_emoji_data = []
		self._load_last_category()
		wx.CallLater(10, self.PostInit)

	def _load_last_category(self):
		"""Reads last category from config and sets the radio box selection."""
		last_category_name = config.conf['emojiMenu']['lastCategory']
		default_category_name = _("All")

		try:
			# Find index, default to 0 ("All") if not found or empty
			index = self.categories.index(last_category_name) if last_category_name in self.categories else 0
		except ValueError:
			index = 0

		if hasattr(self, 'categoryRadioBox') and self.categoryRadioBox.GetCount() > index:
			self.categoryRadioBox.SetSelection(index)
		else:
			wx.CallLater(5, lambda: self.categoryRadioBox.SetSelection(index) if hasattr(self, 'categoryRadioBox') and self.categoryRadioBox.GetCount() > index else None)

	def PostInit(self):
		"""Populates initial list and sets focus."""
		try:
			self._update_emoji_list()
			if hasattr(self, 'searchCtrl'):
				self.searchCtrl.SetFocus()
		except Exception as e:
			ui.message(_("Error initializing emoji list."))
			self.Close()

	def onCharHook(self, event):
		keycode = event.GetKeyCode()

		if keycode == wx.WXK_ESCAPE:
			self.Close() 
		elif keycode == wx.WXK_RETURN:
			self._on_emoji_selected(event)
		else:
			event.Skip()

	def _on_search_text_changed(self, event):
		"""Restarts the timer when search text changes."""
		if self.searchUpdateTimer.IsRunning():
			self.searchUpdateTimer.Stop()
		self.searchUpdateTimer.StartOnce(300)

	def _on_category_changed(self, event):
		"""Saves the new category and schedules list update."""
		if self.searchUpdateTimer.IsRunning():
			self.searchUpdateTimer.Stop()

		try:
			selected_index = self.categoryRadioBox.GetSelection()
			if 0 <= selected_index < len(self.categories):
				selected_category_name = self.categories[selected_index]
				config.conf['emojiMenu']['lastCategory'] = selected_category_name
		except Exception as e:
			pass
		wx.CallLater(0, self._update_emoji_list)

	def _perform_update_list(self, event=None):
		"""Called by the timer or directly to update the list."""
		self._update_emoji_list()

	def _update_emoji_list(self):
		"""Filters and updates the emoji list based on search and category."""
		if not all(hasattr(self, ctrl) for ctrl in ['searchCtrl', 'categoryRadioBox', 'emojiListBox', 'categories']):
			return # Controls or data not ready

		try:
			search_term = self.searchCtrl.GetValue().lower().strip()
			selected_category_index = self.categoryRadioBox.GetSelection()

			if selected_category_index < 0 or selected_category_index >= len(self.categories):
				selected_category = _("All")
				if self.categoryRadioBox.GetCount() > 0: # Ensure radio box is populated
					self.categoryRadioBox.SetSelection(0)
			else:
				selected_category = self.categories[selected_category_index]

			filtered_emojis = []
			for emoji in self.all_emojis:
				is_all_category = selected_category == _("All")
				category_match = is_all_category or emoji.category == selected_category
				if not category_match:
					continue

				search_match = not search_term or \
							   search_term in emoji.name.lower() or \
							   any(search_term in short_name.lower() for short_name in emoji.short_names)
				if not search_match:
					continue

				filtered_emojis.append(emoji)

			self._filtered_emoji_data = [(emoji.name, emoji.char) for emoji in filtered_emojis]

			self.emojiListBox.Freeze()
			self.emojiListBox.Clear()
			if self._filtered_emoji_data:
				self.emojiListBox.AppendItems([name for name, char in self._filtered_emoji_data])
				if self.emojiListBox.GetCount() > 0:
					self.emojiListBox.SetSelection(0)
			self.emojiListBox.Thaw()

		except Exception as e:
			self.emojiListBox.Clear()
			self.emojiListBox.Append(_("Error loading list"))
			if self.emojiListBox.IsFrozen():
				self.emojiListBox.Thaw()

	def _on_emoji_selected(self, event):
		"""Copies the selected emoji to the clipboard and closes the dialog."""
		selection_index = self.emojiListBox.GetSelection()
		if selection_index == wx.NOT_FOUND or selection_index < 0 or selection_index >= len(self._filtered_emoji_data):
			return

		emoji_name, emoji_char = self._filtered_emoji_data[selection_index]
		try:
			if api.copyToClip(emoji_char):
				success_message = _("Emoji copyed to clipboard.")
				ui.message(success_message)
				self.Close()
			else:
				ui.message(_("Failed to copy emoji to clipboard."))
				tones.beep(200, 80)
		except Exception as e:
			ui.message(_("An error occurred while copying."))
			tones.beep(200, 80)

	def onClose(self, event):
		self.Destroy()


class GlobalPlugin(globalPluginHandler.GlobalPlugin):
	@scriptHandler.script(
		description=_("Show Emoji Menu to search and insert emojis"),
		gesture="kb:NVDA+;",
		category=_("Emoji menu")
	)
	def script_showEmojiMenu(self, gesture):
		"""Handles the script gesture to show the Emoji Dialog."""
		def run_dialog():
			try:
				dlg = EmojiDialog(gui.mainFrame)
				dlg.Show() # Show the dialog (non-modal)
			except RuntimeError as e:
				ui.message(_("Emoji library (emoji-data-python) is missing or failed to load."))
				tones.beep(200,80)
			except Exception as e:
				ui.message(_(f"Failed to open Emoji Menu: {e}."))
				tones.beep(200, 80)

		wx.CallLater(0, run_dialog)